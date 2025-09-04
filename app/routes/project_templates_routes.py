from flask import Blueprint, jsonify
from ..utils import token_required
from ..models import ProjectTemplate, TaskTemplate

# Create a new Blueprint for project templates
project_templates_bp = Blueprint('project_templates_bp', __name__)

@project_templates_bp.route('/project-templates', methods=['GET'])
@token_required
def get_project_templates(current_user):
    """
    Retrieves a list of all available project templates with their nested tasks.
    """
    try:
        # Fetch all project templates from the database
        templates = ProjectTemplate.query.all()

        # Helper function to recursively build the JSON for a task and its children
        def _build_task_template_json(task_template):
            # This is the recursive part. Call the function on each child.
            children_json = [_build_task_template_json(child) for child in task_template.children]
            
            # Get the IDs of the tasks this task depends on
            dependency_ids = [dep.id for dep in task_template.dependencies]

            return {
                'id': task_template.id,
                'name': task_template.name,
                'duration_seconds': task_template.duration,
                'parent_id': task_template.parent_id,
                'dependencyIds': dependency_ids,
                'children': children_json
            }

        # Build the final JSON response
        templates_data = []
        for template in templates:
            # For each template, build the JSON for its top-level tasks
            top_level_tasks = [_build_task_template_json(task) for task in template.tasks]
            
            templates_data.append({
                'id': template.id,
                'name': template.name,
                'description': template.description,
                'tasks': top_level_tasks # The full, nested task tree
            })

        return jsonify(templates_data), 200

    except Exception as e:
        print(f"Error fetching project templates: {e}")
        return jsonify({'message': 'Error fetching project templates', 'error': str(e)}), 500