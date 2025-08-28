import os
from app import create_app

# Determine the configuration to use (development, production, etc.)
# You can set FLASK_ENV environment variable or default here.
# config_name = os.getenv('FLASK_ENV', 'development') 
# The config.py already handles defaulting to development if FLASK_ENV is not set.

app = create_app()

if __name__ == '__main__':
    # The port can also be configured via environment variable or directly
    port = int(os.environ.get("PORT", 8080))
    # For development, debug=True is often set in the config.
    # The app.config['DEBUG'] will be True if DevelopmentConfig is used.
    #ssl_context = ('localhost+2.pem', 'localhost+2-key.pem')
    
    app.run(host='0.0.0.0', port=port, debug=app.config.get('DEBUG', False))