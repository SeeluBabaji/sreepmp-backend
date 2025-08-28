from flask import Blueprint, jsonify, request
from ..utils import token_required
from ..rules_engine import get_dashboard_content, get_test_content, submit_test, completed_learning, update_next_recommended_lesson
from .. import db

rules_bp = Blueprint('rules_bp', __name__)

RULES = {
    'dashboard_content': get_dashboard_content,
    'test_content': get_test_content,
    'submit_test': submit_test,
    'completed_learning': completed_learning,
}

@rules_bp.route('/rules/<rule_name>', methods=['GET', 'POST'])
@token_required
def handle_rule(current_user, rule_name):
    """
    Generic route to execute a rule from the rules engine.
    """
    rule = RULES.get(rule_name)
    if not rule:
        return jsonify({'message': 'Rule not found.'}), 404

    if request.method == 'POST':
        if rule_name == 'completed_learning':
            result, status_code = rule(current_user, db)
        else:
            data = request.get_json()
            if not data or 'answers' not in data:
                return jsonify({'message': 'Invalid submission format. Missing "answers" key.'}), 400
            answers = data['answers']
            result, status_code = rule(current_user, answers, db)
        return jsonify(result), status_code

    if rule_name == 'test_content':
        spiral_param = request.args.get('spiral', 'false').lower()
        spiral_mode = spiral_param == 'true'
        result = rule(current_user, spiral=spiral_mode)
    else:
        result = rule(current_user)

    if rule_name == 'test_content':
        return jsonify([question_to_dict(q) for q in result]), 200
    
    return jsonify(result), 200

@rules_bp.route('/rules/update_next_lesson', methods=['POST'])
@token_required
def update_next_lesson_route(current_user):
    data = request.get_json()
    learning_content_id = data.get('learning_content_id')

    response, status_code = update_next_recommended_lesson(current_user, learning_content_id, db)
    return jsonify(response), status_code