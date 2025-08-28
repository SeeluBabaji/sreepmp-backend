# yourapp/google_auth_service.py

from google.oauth2 import id_token
from google.auth.transport import requests
from flask import current_app

class GoogleAuthService:
    @staticmethod
    def verify_token(token):
        """
        Verifies a Google ID token and returns the user's info.
        :param token: The ID token sent from the client.
        :return: A dictionary with user info if valid, otherwise raises an error.
        """
        try:
            # Specify the CLIENT_ID of the app that accesses the backend.
            # This is a crucial security step.
            client_id = current_app.config['GOOGLE_CLIENT_ID']
            
            # The 'requests.Request()' object is used to make the verification request.
            id_info = id_token.verify_oauth2_token(token, requests.Request(), client_id, clock_skew_in_seconds=10)
            
            # The id_info dictionary contains the decoded JWT payload from Google.
            # Example: {'iss': '...', 'azp': '...', 'aud': '...', 'sub': '...', 'email': '...', 'name': '...', ...}
            return id_info

        except ValueError as e:
            # This can happen if the token is invalid, expired, or for the wrong audience.
            current_app.logger.error(f"Google token verification failed: {e}")
            raise ValueError("Invalid Google token.")
        except Exception as e:
            current_app.logger.error(f"An unexpected error occurred during Google token verification: {e}")
            raise Exception("Could not verify Google token.")