from flask import Flask, send_from_directory
import os
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import app_config # Import the configuration we created

# Initialize extensions
db = SQLAlchemy()

def create_app(config_name=None):
    """
    Application factory function.
    Initializes the Flask app, extensions, and registers blueprints.
    """
    app = Flask(__name__)

    # Load configuration
    # If config_name is not provided, it defaults to DevelopmentConfig via config.py
    current_config = app_config 
    if config_name == 'production':
        from config import ProductionConfig
        current_config = ProductionConfig()
    elif config_name == 'development':
        from config import DevelopmentConfig
        current_config = DevelopmentConfig()
        
    app.config.from_object(current_config)

    # Initialize extensions with the app
    db.init_app(app)
    CORS(app, origins="*")

    # Import and register blueprints here
    from .routes.auth_routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')

  
    from .routes.rules_routes import rules_bp
    app.register_blueprint(rules_bp, url_prefix='/api/v1')

    # from .routes.user_routes import user_bp # Example for user specific routes
    # app.register_blueprint(user_bp, url_prefix='/api/v1/users')


    @app.route('/health')
    def health_check():
        return "API is healthy!", 200

    @app.route('/images/<filename>')
    def serve_image(filename):
        return send_from_directory(os.path.join(app.root_path, '..', 'images'), filename)

    return app