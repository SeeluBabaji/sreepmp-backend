from flask import Blueprint, request, jsonify
from ..utils import token_required
from .. import db
from ..models import Project, Account, User
import datetime

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
        db.session.commit()
        return jsonify({
            'message': 'Project created successfully',
            'project': {
                'id': new_project.id,
                'name': new_project.name,
                'description': new_project.description,
                'start_date': new_project.start_date.isoformat() if new_project.start_date else None,
                'end_date': new_project.end_date.isoformat() if new_project.end_date else None,
                'account_id': new_project.account_id,
                'created_by': new_project.created_by,
                'created_at': new_project.created_at.isoformat(),
                'updated_at': new_project.updated_at.isoformat()
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error creating project', 'error': str(e)}), 500
