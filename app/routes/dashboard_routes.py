from flask import Blueprint, jsonify
from ..utils import token_required
from ..rules_engine import get_dashboard_content

dashboard_bp = Blueprint('dashboard_bp', __name__)

@dashboard_bp.route('/dashboard', methods=['GET'])
@token_required
def dashboard(current_user):
    """
    Returns the content for the user's dashboard.
    """
    content = get_dashboard_content(current_user)
    return jsonify(content), 200