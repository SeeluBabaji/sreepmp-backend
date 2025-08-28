import jwt
import datetime
import os
from flask import current_app, jsonify, request
from functools import wraps
from .models import User # Assuming your User model is in models.py

def generate_token(user_id, user_email, secret_key):
    """
    Generates the Auth Token
    :return: string
    """
    try:
       
        # Get the current time as a UTC datetime object
        current_time_utc = datetime.datetime.utcnow()
        
        # Convert it to an integer Unix timestamp (seconds since epoch)
        # This is a robust way to do it. (-15 to allow for issuing in the past ....7/6/2025)
        iat_timestamp = int(current_time_utc.timestamp()) - 15
        
        # Calculate the expiration time
        exp_time_utc = current_time_utc + datetime.timedelta(days=1)
        exp_timestamp = int(exp_time_utc.timestamp())
       # payload = {
       #     'exp': int((datetime.datetime.utcnow() + datetime.timedelta(days=1)).timestamp()),
       #     'iat': int((datetime.datetime.utcnow() - datetime.timedelta(seconds=5)).timestamp()),
       #     'sub': user_id, # Subject of the token is the user ID
       #     'email': user_email # Include email for convenience, if needed
       # }
        payload = {
            'exp': exp_timestamp,
            'iat': iat_timestamp,
            'sub': str(user_id), # Subject of the token is the user ID
            'email': user_email # Include email for convenience, if needed
        }
        
        #print(int((datetime.datetime.utcnow() - datetime.timedelta(seconds=5)).timestamp())+"vs"+iat_timestamp)
        return jwt.encode(
            payload,
            secret_key.encode('utf-8'),
            #secret_key,
            algorithm='HS256'
        )
    except Exception as e:
        return str(e)
# utils.py

def decode_token_DIAGNOSTIC(token, secret_key):
    """
    Decodes the auth token, explicitly disabling the iat check for diagnostics.
    """
    try:
        # --- THE DIAGNOSTIC CODE ---
        # This options dictionary tells the decoder what to verify.
        decode_options = {
            "verify_exp": True,  # We still want to check the expiration time.
            "verify_iat": False, # THIS IS THE KEY: We are turning OFF the "issued at" check.
            "verify_signature": True # We absolutely want to verify the signature.
        }
        
        secret_key_bytes = secret_key.encode('utf-8')
        
        current_app.logger.info("--- DECODING WITH IAT VALIDATION DISABLED ---")
        
        payload = jwt.decode(
            token,
            secret_key_bytes,
            algorithms=['HS256'],
            leeway=60, # Leeway is now ignored for iat, but it's good to keep it for exp.
            options=decode_options
        )
        
        current_app.logger.info("--- SUCCESS! DECODE WORKED WITH IAT CHECK OFF ---")
        return payload

    except jwt.InvalidTokenError as e:
        # Now we'll see the REAL error if it's not the iat.
        current_app.logger.error(f"--- FAILED EVEN WITH IAT CHECK OFF: {e} ---")
        return 'Invalid token. Please log in again.'
    except Exception as e:
        current_app.logger.error(f"--- UNEXPECTED DECODE ERROR: {e} ---")
        return 'An unexpected error occurred.'
def decode_token_SUPERDIAGNOSTIC(token, secret_key):
    """
    Decodes the auth token, explicitly disabling the iat check for diagnostics. 
    # TODO this  after some progress with the features to troubleshoot why iat cannot be decoded successfully for the JWT token
    """
    try:
        # --- THE DIAGNOSTIC CODE ---
        # This options dictionary tells the decoder what to verify.
        decode_options = {
            "verify_exp": True,  # We still want to check the expiration time.
            "verify_iat": False, # THIS IS THE KEY: We are turning OFF the "issued at" check.
            "verify_signature": True # We absolutely want to verify the signature.
        }
        
        secret_key_bytes = secret_key.encode('utf-8')
        
        current_app.logger.info("--- DECODING WITH IAT VALIDATION DISABLED ---")
        unverified_payload = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
        token_iat = unverified_payload.get('iat')

        # 2. Get the current time exactly as the validation logic would.
        current_time = int(time.time())
        
        # 3. Get the leeway
        leeway = 60 # Using a large leeway for this test

        # 4. Log everything
        current_app.logger.info("--- IAT VALIDATION DEBUG ---")
        current_app.logger.info(f"Token 'iat' Claim:      {token_iat}")
        current_app.logger.info(f"Current System Time:    {current_time}")
        current_app.logger.info(f"Leeway:                 {leeway}")
        
        # 5. Manually perform the check that PyJWT does internally
        # The check is: Is the "issued at" time greater than the current time plus leeway?
        is_invalid = token_iat > (current_time + leeway)
        time_difference = token_iat - current_time
        
        current_app.logger.info(f"Time Difference (iat - now): {time_difference} seconds")
        current_app.logger.info(f"Is token invalid (iat > now + leeway)? -> {is_invalid}")
        current_app.logger.info("-----------------------------")

        # --- END DIAGNOSTICS ---

        payload = jwt.decode(
            token,
            secret_key_bytes,
            algorithms=['HS256'],
            leeway=60, # Leeway is now ignored for iat, but it's good to keep it for exp.
            options=decode_options
        )
        
        current_app.logger.info("--- SUCCESS! DECODE WORKED WITH IAT CHECK OFF ---")
        return payload

    except jwt.InvalidTokenError as e:
        # Now we'll see the REAL error if it's not the iat.
        current_app.logger.error(f"--- FAILED EVEN WITH IAT CHECK OFF: {e} ---")
        return 'Invalid token. Please log in again.'
    except Exception as e:
        current_app.logger.error(f"--- UNEXPECTED DECODE ERROR: {e} ---")
        return 'An unexpected error occurred.'
def decode_token(token, secret_key):
    """
    Decodes the auth token, explicitly disabling the iat check for diagnostics.
    """
    try:
        # --- THE DIAGNOSTIC CODE ---
        # This options dictionary tells the decoder what to verify.
        # Get the verify_iat setting from environment variables, default to False
        verify_iat_str = os.environ.get('VERIFY_IAT', 'false').lower()
        verify_iat_bool = verify_iat_str == 'true'

        decode_options = {
            "verify_exp": True,  # We still want to check the expiration time.
            "verify_iat": verify_iat_bool, # Controlled by VERIFY_IAT env var
            "verify_signature": True # We absolutely want to verify the signature.
        }
        
        secret_key_bytes = secret_key.encode('utf-8')
        
        current_app.logger.info("--- DECODING WITH IAT VALIDATION DISABLED ---")
        
        payload = jwt.decode(
            token,
            secret_key_bytes,
            algorithms=['HS256'],
            leeway=60, # Leeway is now ignored for iat, but it's good to keep it for exp.
            options=decode_options
        )
        
        current_app.logger.info("--- SUCCESS! DECODE WORKED WITH IAT CHECK OFF ---")
        return payload

    except jwt.InvalidTokenError as e:
        # Now we'll see the REAL error if it's not the iat.
        current_app.logger.error(f"--- FAILED EVEN WITH IAT CHECK OFF: {e} ---")
        return 'Invalid token. Please log in again.'
    except Exception as e:
        current_app.logger.error(f"--- UNEXPECTED DECODE ERROR: {e} ---")
        return 'An unexpected error occurred.'

def decode_token_original(token, secret_key):
    """
    Decodes the auth token
    :param token:
    :return: integer|string
    """
    try:
        current_app.logger.info("At decode "+secret_key)
        payload = jwt.decode(token, secret_key.encode('utf-8'), algorithms=['HS256'], leeway=60)
        #payload = jwt.decode(token, secret_key, algorithms=['HS256'], leeway=60)
        return payload
    except jwt.ExpiredSignatureError as e:
        current_app.logger.info("-------------jwt.ExpiredSignatureError")
        current_app.logger.error (e)
        return 'Signature expired. Please log in again.'
    except jwt.InvalidTokenError as e:
        current_app.logger.info("-------------jwt.InvalidTokenError")
        current_app.logger.error (e)
        return 'Invalid token. Please log in again.'


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # Check for token in 'Authorization' header (Bearer token)
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Bearer token malformed!'}), 401
        
        if not token:
            # Fallback to check 'x-access-token' header for compatibility or other use cases
            if 'x-access-token' in request.headers:
                token = request.headers['x-access-token']

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            secret_key = current_app.config.get('SECRET_KEY')
            data = decode_token(token, secret_key)
            if isinstance(data, str): # Error message returned from decode_token
                return jsonify({'message': data}), 401
            
            current_app.logger.info(f"Attempting to find user with sub: {data['sub']} (type: {type(data['sub'])})")
            current_user = User.query.filter_by(id=data['sub']).first()
            if not current_user:
                current_app.logger.error(f"User with id {data['sub']} was not found in the database.")
                return jsonify({'message': 'User not found!'}), 401
            current_app.logger.info(f"Successfully found user: {current_user.email}")
                
        except Exception as e:
            current_app.logger.error(f"Token processing error: {e}")
            return jsonify({'message': 'Token is invalid or expired!'}), 401

        return f(current_user, *args, **kwargs) # Pass the user object to the decorated function

    return decorated