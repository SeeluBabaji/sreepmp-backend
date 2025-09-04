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

@projects_bp.route('/projects', methods=['GET'])
@token_required
def get_projects(current_user):
    """
    Retrieves a list of projects for the currently selected account of the user.
    Requires 'account_id' as a query parameter.
    """
    account_id_str = request.args.get('account_id')

    if not account_id_str:
        return jsonify({'message': 'Account ID is required as a query parameter'}), 400

    try:
        account_id = int(account_id_str)
    except ValueError:
        return jsonify({'message': 'Invalid Account ID format. Must be an integer.'}), 400

    # Ensure the current user is authorized for this account
    user_account_ids = [ua.account_id for ua in current_user.accounts]
    if account_id not in user_account_ids:
        return jsonify({'message': 'User not authorized for this account'}), 403

    try:
        projects = Project.query.filter_by(account_id=account_id).all()

        projects_data = [{
            'id': project.id,
            'name': project.name,
            'description': project.description,
            'start_date': project.start_date.isoformat() if project.start_date else None,
            'end_date': project.end_date.isoformat() if project.end_date else None,
            'account_id': project.account_id,
            'created_by': project.created_by,
            'created_at': project.created_at.isoformat(),
            'updated_at': project.updated_at.isoformat()
        } for project in projects]

        return jsonify(projects_data), 200

    except Exception as e:
        print(f"Error fetching projects: {e}")
        return jsonify({'message': 'Error fetching projects', 'error': str(e)}), 500

@projects_bp.route('/projects/<int:project_id>', methods=['PUT'])
@token_required
def update_project(current_user, project_id):
    """
    Updates an existing project by correctly deleting and recreating tasks to
    respect foreign key constraints.
    """
    project = Project.query.get(project_id)
    if not project:
        return jsonify({'message': 'Project not found'}), 404

    # ... Authorization check ...

    data = request.get_json()
    if not data:
        return jsonify({'message': 'No input data provided'}), 400

    try:
        # 1. Update Project-level fields
        project.name = data.get('name', project.name)
        project.description = data.get('description', project.description)
        project.updated_at = datetime.datetime.now(datetime.timezone.utc)

        tasks_data = data.get('tasks', [])
        
        # 2. Delete existing tasks correctly (from previous fix)
        existing_tasks = Task.query.filter_by(project_id=project_id).all()
        tasks_to_delete = list(existing_tasks)
        while tasks_to_delete:
            parent_ids = {task.parent_id for task in tasks_to_delete if task.parent_id is not None}
            deletable_tasks = [task for task in tasks_to_delete if task.id not in parent_ids]
            
            if not deletable_tasks:
                 raise Exception("Cannot delete tasks due to a circular parent-child relationship.")
            
            for task in deletable_tasks:
                task.dependencies.clear()
                task.dependents.clear()
                db.session.delete(task)
            
            tasks_to_delete = [t for t in tasks_to_delete if t not in deletable_tasks]
        db.session.flush()

        # 3. --- RECREATE ALL TASKS (NEW, ROBUST LOGIC) ---
        
        # First Pass: Create all task objects without parent links
        frontend_id_map = {} # Maps frontend UUID -> newly created backend Task object
        for task_data in tasks_data:
            new_task = Task(
                project_id=project.id,
                name=task_data.get('name'),
                status=TaskStatusEnum[task_data.get('status', 'NOT_STARTED').upper()],
                start_date=datetime.datetime.fromisoformat(task_data.get('start_date').replace('Z', '+00:00')),
                duration=task_data.get('duration')
            )
            db.session.add(new_task)
            frontend_id_map[task_data.get('frontend_id')] = new_task
            
        db.session.flush() # Assign database IDs to all newly created tasks

        # Second Pass: Link parents and dependencies now that all tasks exist
        for task_data in tasks_data:
            frontend_id = task_data.get('frontend_id')
            task_to_update = frontend_id_map.get(frontend_id)
            if not task_to_update: continue

            # Link Parent
            parent_frontend_id = task_data.get('parent_id')
            if parent_frontend_id and parent_frontend_id in frontend_id_map:
                parent_task = frontend_id_map[parent_frontend_id]
                task_to_update.parent_id = parent_task.id
            
            # Link Dependencies
            dependency_data = task_data.get('dependencies', [])
            for dep in dependency_data:
                dep_frontend_id = dep.get('depends_on_task_id')
                prerequisite_task = frontend_id_map.get(str(dep_frontend_id))
                if prerequisite_task:
                    task_to_update.dependencies.append(prerequisite_task)
        
        db.session.commit()
        return jsonify({'message': 'Project updated successfully'}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error updating project: {e}")
        return jsonify({'message': 'An internal error occurred while updating the project', 'error': str(e)}), 500
    
@projects_bp.route('/projects/<int:project_id>', methods=['GET'])
@token_required
def get_project(current_user, project_id):
    """
    Retrieves a single project by its ID.
    """
    try:
        project = Project.query.get(project_id)

        if not project:
            return jsonify({'message': 'Project not found'}), 404

        # Ensure the current user is authorized for this project's account
        user_account_ids = [ua.account_id for ua in current_user.accounts]
        if project.account_id not in user_account_ids:
            return jsonify({'message': 'User not authorized to view this project'}), 403

        def _build_task_json(task):
            task_json = {
                'id': task.id,
                'name': task.name,
                'description': task.description,
                'status': task.status.name,
                'startDate': task.start_date.isoformat() if task.start_date else None,
                'duration': task.duration, # Duration in seconds
                'projectId': task.project_id,
                'parentId': task.parent_id,
                'assignedTo': task.assigned_to,
                'dependencyIds': [dep.id for dep in task.dependencies],
                'children': [], # Will be populated recursively
            }
            return task_json

        # Fetch all tasks for the project
        all_tasks = Task.query.filter_by(project_id=project_id).all()
        
        # Create a map for quick lookup and to store the JSON representation
        task_map = {task.id: _build_task_json(task) for task in all_tasks}

        # Build the hierarchy
        for task in all_tasks:
            if task.parent_id and task.parent_id in task_map:
                task_map[task.parent_id]['children'].append(task_map[task.id])
            # If a task has no parent_id, it's a top-level task.
            # We don't need to explicitly add it to a top-level list here,
            # as the frontend's _buildTaskHierarchy will handle it.
            # However, we need to ensure all tasks are included in the 'tasks' list.

        # Flatten the task_map values into a list for the frontend
        # The frontend's _buildTaskHierarchy will reconstruct the tree
        tasks_list_for_frontend = list(task_map.values())

        project_data = {
            'id': project.id,
            'name': project.name,
            'description': project.description,
            'start_date': project.start_date.isoformat() if project.start_date else None,
            'end_date': project.end_date.isoformat() if project.end_date else None,
            'account_id': project.account_id,
            'created_by': project.created_by,
            'created_at': project.created_at.isoformat(),
            'updated_at': project.updated_at.isoformat(),
            'tasks': tasks_list_for_frontend # Include the tasks here
        }
        return jsonify(project_data), 200

    except Exception as e:
        print(f"Error fetching project by ID: {e}")
        return jsonify({'message': 'Error fetching project', 'error': str(e)}), 500
