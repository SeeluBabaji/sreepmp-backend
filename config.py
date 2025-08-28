import os
from dotenv import load_dotenv

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')

    print(f"DEBUG: Config.SQLALCHEMY_DATABASE_URI is: {SQLALCHEMY_DATABASE_URI}")
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    # Add any production-specific settings here, e.g.
    # SQLALCHEMY_POOL_RECYCLE = 299
    # SQLALCHEMY_ENGINE_OPTIONS = {'pool_recycle': 280}


# Determine which config to use based on FLASK_ENV or default to Development
FLASK_ENV = os.environ.get('FLASK_ENV', 'development')

if FLASK_ENV == 'production':
    app_config = ProductionConfig()
else:
    app_config = DevelopmentConfig()