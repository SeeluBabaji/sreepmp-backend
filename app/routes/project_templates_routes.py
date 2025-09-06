from flask import Blueprint, jsonify
from ..utils import token_required
from ..models import ProjectTemplate, TaskTemplate

# Create a new Blueprint for project templates
project_templates_bp = Blueprint('project_templates_bp', __name__)


# --- NEW: Route 1 - Get a lightweight list of all templates ---

@project_templates_bp.route('/project-templates', methods=['GET'])
@token_required
def get_project_template_list(current_user):
    """
    Retrieves a lightweight list of all available project templates,
    containing only their ID, name, and description.
    """
    try:
        # Fetch all project templates from the database
        templates = ProjectTemplate.query.all()

        # Build a simple list of dictionaries, without the heavy task data
        templates_data = [{
            'id': template.id,
            'name': template.name,
            'description': template.description
        } for template in templates]

        return jsonify(templates_data), 200

    except Exception as e:
        print(f"Error fetching project template list: {e}")
        return jsonify({'message': 'Error fetching project templates', 'error': str(e)}), 500


# --- NEW: Route 2 - Get the full details of a single template ---

@project_templates_bp.route('/project-templates/<int:template_id>', methods=['GET'])
@token_required
def get_project_template_details(current_user, template_id):
    """
    Retrieves the full details, including the nested task tree, for a
    single project template by its ID.
    """
    try:
        # Fetch the specific project template by its ID
        template = ProjectTemplate.query.get(template_id)

        if not template:
            return jsonify({'message': 'Project template not found'}), 404

        # Helper function to recursively build the JSON for a task and its children
        # This is the same powerful function from your original route
        def _build_task_template_json(task_template):
            children_json = [_build_task_template_json(child) for child in task_template.children]
            dependency_ids = [dep.id for dep in task_template.dependencies]

            return {
                'id': task_template.id,
                'name': task_template.name,
                'duration_seconds': task_template.duration,
                'parent_id': task_template.parent_id,
                'dependencyIds': dependency_ids,
                'children': children_json
            }

        # Build the JSON for the template's top-level tasks
        top_level_tasks = [_build_task_template_json(task) for task in template.tasks]
        
        # Assemble the final data for the single template
        template_details = {
            'id': template.id,
            'name': template.name,
            'description': template.description,
            'tasks': top_level_tasks # The full, nested task tree
        }

        return jsonify(template_details), 200

    except Exception as e:
        print(f"Error fetching project template details for ID {template_id}: {e}")
        return jsonify({'message': 'Error fetching project template details', 'error': str(e)}), 500