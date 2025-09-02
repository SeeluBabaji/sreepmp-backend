from flask import Blueprint, request, jsonify
from ..utils import token_required
from .. import db
from ..models import Project, Account, User, Task, TaskStatusEnum
import datetime
from collections import deque

projects_bp = Blueprint('projects_bp', __name__)

@projects_bp.route('/projects', methods=['POST'])
@token_required
def create_project(current_user):
    """
    Creates a new project.
    """
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No input data provided'}), 400

    name = data.get('name')
    description = data.get('description')
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')
    account_id = data.get('account_id')
    tasks_data = data.get('tasks', []) # Get tasks data, default to empty list

    if not name or not account_id:
        return jsonify({'message': 'Project name and account ID are required'}), 400

    # Validate account_id
    account = Account.query.get(account_id)
    if not account:
        return jsonify({'message': 'Account not found'}), 404
    
    # Ensure the current user is associated with the account
    user_accounts = [ua.account_id for ua in current_user.accounts]
    if account_id not in user_accounts:
        return jsonify({'message': 'User not authorized for this account'}), 403

    start_date = None
    if start_date_str:
        try:
            start_date = datetime.datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'message': 'Invalid start_date format. Use ISO 8601.'}), 400

    end_date = None
    if end_date_str:
        try:
            end_date = datetime.datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'message': 'Invalid end_date format. Use ISO 8601.'}), 400

    new_project = Project(
        name=name,
        description=description,
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        created_by=current_user.id
    )

    try:
        db.session.add(new_project)
        db.session.flush() # Flush to get new_project.id before committing

        # Dictionary to map frontend UUIDs to backend integer IDs
        frontend_id_to_backend_task = {}
        
        # Use a deque for BFS-like processing to ensure parents are processed before children
        # Each item in the deque will be (task_data_from_frontend, parent_backend_id)
        q = deque([(task_data, None) for task_data in tasks_data if task_data.get('parent_id') is None])

        # Add children to the queue, ensuring all top-level tasks are processed first
        # This handles the case where tasks_data might not be perfectly ordered
        processed_frontend_ids = set(task_data.get('id') for task_data in tasks_data if task_data.get('parent_id') is None)
        
        while q:
            task_data, parent_backend_id = q.popleft()
            
            frontend_task_id = task_data.get('id')
            task_name = task_data.get('name')
            task_status_str = task_data.get('status', 'NOT_STARTED').upper()
            task_start_date_str = task_data.get('startDate')
            task_duration_seconds = task_data.get('duration') # Duration is already in seconds from frontend

            if not task_name:
                raise ValueError(f"Task name is required for task with frontend ID {frontend_task_id}")

            try:
                task_status = TaskStatusEnum[task_status_str]
            except KeyError:
                raise ValueError(f"Invalid task status: {task_status_str}")

            task_start_date = None
            if task_start_date_str:
                try:
                    task_start_date = datetime.datetime.fromisoformat(task_start_date_str.replace('Z', '+00:00'))
                except ValueError:
                    raise ValueError(f"Invalid task start_date format for task {task_name}. Use ISO 8601.")

            new_task = Task(
                name=task_name,
                status=task_status,
                start_date=task_start_date,
                duration=task_duration_seconds,
                project_id=new_project.id,
                parent_id=parent_backend_id,
                assigned_to=None # Assuming no assignment during creation
            )
            db.session.add(new_task)
            db.session.flush() # Flush to get new_task.id

            frontend_id_to_backend_task[frontend_task_id] = new_task

            # Add children of the current task to the queue
            for child_task_data in tasks_data:
                if child_task_data.get('parent_id') == frontend_task_id and child_task_data.get('id') not in processed_frontend_ids:
                    q.append((child_task_data, new_task.id))
                    processed_frontend_ids.add(child_task_data.get('id'))

        # Process dependencies after all tasks are created and have backend IDs
        for task_data in tasks_data:
            frontend_task_id = task_data.get('id')
            backend_task = frontend_id_to_backend_task.get(frontend_task_id)
            if backend_task:
                dependency_ids_frontend = task_data.get('dependencyIds', [])
                for dep_frontend_id in dependency_ids_frontend:
                    dependent_backend_task = frontend_id_to_backend_task.get(dep_frontend_id)
                    if dependent_backend_task:
                        backend_task.dependencies.append(dependent_backend_task)
                    else:
                        print(f"Warning: Frontend dependency ID {dep_frontend_id} not found in backend tasks.")
        
        db.session.commit()

        return jsonify({
            'message': 'Project and tasks created successfully',
            'project': {
                'id': new_project.id,
                'name': new_project.name,
                'description': new_project.description,
                'start_date': new_project.start_date.isoformat() if new_project.start_date else None,
                'end_date': new_project.end_date.isoformat() if new_project.end_date else None,
                'account_id': new_project.account_id,
                'created_by': new_project.created_by,
                'created_at': new_project.created_at.isoformat(),
                'updated_at': new_project.updated_at.isoformat(),
                'tasks_count': len(frontend_id_to_backend_task)
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error during project creation: {e}")
        return jsonify({'message': 'Error creating project and tasks', 'error': str(e)}), 500
