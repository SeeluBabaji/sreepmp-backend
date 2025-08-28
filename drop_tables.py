from app import create_app, db
from sqlalchemy import text, inspect

def drop_all_tables():
    """Drops all tables from the database."""
    app = create_app()
    with app.app_context():
        with db.engine.connect() as connection:
            with connection.begin() as transaction:
                try:
                    print("Disabling foreign key checks...")
                    connection.execute(text('SET FOREIGN_KEY_CHECKS = 0;'))
                    
                    print("Fetching all table names...")
                    inspector = inspect(db.engine)
                    tables = inspector.get_table_names()
                    
                    print("Dropping all tables...")
                    for table in tables:
                        print(f"Dropping table {table}")
                        connection.execute(text(f'DROP TABLE IF EXISTS `{table}`;'))

                    print("Enabling foreign key checks...")
                    connection.execute(text('SET FOREIGN_KEY_CHECKS = 1;'))
                    
                    print("All tables dropped successfully.")
                except Exception as e:
                    print(f"An error occurred: {e}")

if __name__ == '__main__':
    drop_all_tables()