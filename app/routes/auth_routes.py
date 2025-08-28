from flask import Blueprint, request, jsonify, current_app
from ..models import User, UserProfile, UserCommunicationPreferences, AuthCode, Account, UserAccount
from datetime import datetime, timezone
from .. import db # Import db instance from app/__init__.py
from ..utils import generate_token, token_required
from ..google_auth_service import GoogleAuthService # Our new service


auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/google', methods=['POST'])
def google_auth():
    """
    Handles authentication via a Google ID Token sent from the client.
    """
    data = request.get_json()
    google_token = data.get('token')

    if not google_token:
        return jsonify({'message': 'Google token is missing!'}), 400

    try:
        # 1. Verify the Google token using our service
        user_info = GoogleAuthService.verify_token(google_token)

        # 2. Check if user exists in our database
        user = User.query.filter_by(email=user_info['email']).first()
        newuser_flag = False
        if not user:
            # 3a. If user doesn't exist, create a new one
            current_app.logger.info(f"Creating new user for email: {user_info['email']}")
            new_user = User(
                
                email=user_info['email'],
                auth_source='GOOGLE',
                name=user_info.get('name', ''), 
                organization_id = 1, # Use .get for optional fields
                # NOTE: You need a way to handle passwords for users who sign up this way.
                # A common strategy is to leave the password hash null or set it to an
                # unusable value, as they will never log in with a password.
                password_hash=None # Or some other indicator of social login
            )
            db.session.add(new_user)
           
         
            db.session.commit()
            user = new_user
            newuser_flag = True
        # 4. Generate our OWN internal JWT for the user
        secret_key = current_app.config.get('SECRET_KEY')
        internal_token = generate_token(user.id, user.email, secret_key)
        current_app.logger.info(f"User {user.email} authenticated via Google successfully.")

        # 5. Return our internal token to the client
        return jsonify({
            'message': 'Authentication successful!',
            'token': internal_token,
            'user': {'id': user.id, 'email': user.email, 'newuser' :newuser_flag } # Send back user info
        }), 200

    except ValueError as e:
        # This catches the "Invalid Google token" error from our service
        return jsonify({'message': str(e)}), 401
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred in Google auth: {e}", exc_info=True)
        return jsonify({'message': 'An internal error occurred.'}), 500


#  now likely comment out or remove  old password-based login
# @auth_bp.route('/login', methods=['POST'])
# def login():
#     # ... old code ...

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Email and password are required!'}), 400

    user = User.query.filter_by(email=data['email']).first()

    if not user:
        current_app.logger.info(f"Login attempt for non-existent user: {data['email']}")
        return jsonify({'message': 'Invalid credentials!'}), 401 # User not found

    if user.check_password(data['password']):
        # Password matches, generate token
        try:
            token = generate_token(user.id, user.email)
            current_app.logger.info(f"User {user.email} logged in successfully.")
            return jsonify({'message': 'Login successful!', 'token': token}), 200
        except Exception as e:
            current_app.logger.error(f"Token generation error for user {user.email}: {e}")
            return jsonify({'message': 'Could not generate token, login failed.'}), 500
    else:
        current_app.logger.warning(f"Failed login attempt for user: {data['email']}")
        return jsonify({'message': 'Invalid credentials!'}), 401 # Incorrect password

# Example of a protected route (can be moved to a different blueprint)
# from ..utils import token_required
# @auth_bp.route('/test_protected', methods=['GET'])
# @token_required
# def test_protected_route(current_user): # current_user is passed by the decorator
#     return jsonify({'message': f'Hello {current_user.email}! This is a protected route.'}), 200

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    """
    Returns the details of the currently authenticated user.
    """
    if not current_user:
        return jsonify({'message': 'User not found.'}), 404
    

    accounts_data = []
    for user_account in current_user.accounts:
        account = user_account.account
        if account:
            accounts_data.append({
                'account_id': account.id,
                'account_name': account.name,
                'role': user_account.role
            })

    return jsonify({
        'id': current_user.id,
        'email': current_user.email,
       
        'accounts': accounts_data
    }), 200

@auth_bp.route('/me/profile', methods=['PUT'])
@token_required
def update_user_profile(current_user):
    """
    Updates the profile of the currently authenticated user.
    """
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Request body is missing.'}), 400

    profile = current_user.profile
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.session.add(profile)

    try:
        db.session.commit()
        return jsonify({'message': 'Profile updated successfully.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating profile for user {current_user.email}: {e}")
        return jsonify({'message': 'Failed to update profile.'}), 500

@auth_bp.route('/me/communication_preferences', methods=['PUT'])
@token_required
def update_user_communication_preferences(current_user):
    """
    Updates the communication preferences of the currently authenticated user.
    """
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Request body is missing.'}), 400

    prefs = current_user.communication_preferences
    if not prefs:
        prefs = UserCommunicationPreferences(user_id=current_user.id)
        db.session.add(prefs)

    prefs.parent_email = data.get('parent_email', prefs.parent_email)
    prefs.primary_notification_email = data.get('primary_notification_email', prefs.primary_notification_email)
    prefs.primary_contact_phone = data.get('primary_contact_phone', prefs.primary_contact_phone)

    try:
        db.session.commit()
        return jsonify({'message': 'Communication preferences updated successfully.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating communication preferences for user {current_user.email}: {e}")
        return jsonify({'message': 'Failed to update communication preferences.'}), 500

@auth_bp.route('/activate_account', methods=['POST'])
@token_required
def activate_account(current_user):
    """
    Activates a user's account using an authentication code.
    """
    data = request.get_json()
    auth_code_str = data.get('auth_code')

    if not auth_code_str:
        return jsonify({'message': 'Auth code is required.'}), 400

    auth_code_entry = AuthCode.query.filter_by(authcode=auth_code_str).first()

    if not auth_code_entry:
        return jsonify({'message': 'Invalid or expired auth code.'}), 404

    if auth_code_entry.expires_at.date() < datetime.now(timezone.utc).date():
        db.session.delete(auth_code_entry)
        db.session.commit()
        return jsonify({'message': 'Auth code has expired.'}), 400

    # Check if the user is already associated with this account
    existing_user_account = UserAccount.query.filter_by(
        user_id=current_user.id,
        account_id=auth_code_entry.account_id
    ).first()

    if existing_user_account:
        db.session.delete(auth_code_entry)
        db.session.commit()
        return jsonify({'message': 'User is already associated with this account.'}), 409 # Conflict

    # Associate the user with the account
    new_user_account = UserAccount(
        user_id=current_user.id,
        account_id=auth_code_entry.account_id,
        role=auth_code_entry.role
    )
    db.session.add(new_user_account)
    db.session.delete(auth_code_entry) # Auth code is single-use

    try:
        db.session.commit()
        return jsonify({'message': 'Account activated successfully.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error activating account for user {current_user.email} with code {auth_code_str}: {e}")
        return jsonify({'message': 'Failed to activate account.'}), 500