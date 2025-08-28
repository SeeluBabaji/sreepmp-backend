from app import create_app, db
from app.models import *

# Create a new Flask app instance
# FLASK_ENV can be set to 'development' or 'production' if needed for specific configs
# but for create_all, the default config loaded by create_app() should be fine
# as long as DATABASE_URL is correctly set in .env
app = create_app()

with app.app_context():
    print("Attempting to create database tables...")
    try:
        # This will create tables based on your SQLAlchemy models
        # if they don't already exist.
        db.create_all()
        print("Database tables process completed. Check your database to confirm.")
    except Exception as e:
        print(f"An error occurred during table creation: {e}")
        print("Please ensure your DATABASE_URL in .env is correct and the database server is running.")

if __name__ == '__main__':
    # The main logic for table creation is within app.app_context() above.
    # This block just confirms the script has run.
    print("create_tables.py script has finished execution.")