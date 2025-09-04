import os
import pandas as pd
import argparse
import datetime # Import datetime
from sqlalchemy import text
from app import create_app, db
from app.models import Organization, AuthCode, Account, User,ProjectTemplate, TaskTemplate # Import necessary models
#insert into organizations values (1,'org1','address1',null)
def seed_data(delete=False):
    """Seeds the database with data from CSV files."""
    app = create_app()
    with app.app_context():
        if delete:
            print("Deleting old data and resetting identity counters...")
            # For MySQL, we need to truncate tables one by one and disable foreign key checks.
            # TRUNCATE TABLE automatically resets the AUTO_INCREMENT counter in MySQL.
            table_names = [
                'auth_codes', 'user_accounts', 'accounts', 'organizations', 'users'
            ] # Include tables in correct order for foreign key constraints

            db.session.execute(text('SET FOREIGN_KEY_CHECKS = 0;'))
            for table_name in table_names:
                db.session.execute(text(f'TRUNCATE TABLE {table_name};'))
            db.session.execute(text('SET FOREIGN_KEY_CHECKS = 1;'))
            db.session.commit()
            print("Old data deleted and identity counters reset.")

        # Seed Organizations
        if Organization.query.first() is None:
            df = pd.read_csv('seed/data/organizations.csv', skipinitialspace=True)
            for _, row in df.iterrows():
                organization = Organization(
                    name=row['name']
                )
                db.session.add(organization)
            db.session.commit()
            print("Seeded Organizations")

        # Seed Accounts
        if Account.query.first() is None:
            df = pd.read_csv('seed/data/accounts.csv', skipinitialspace=True)
            df.dropna(how='all', inplace=True) # Remove empty rows
            for _, row in df.iterrows():
                organization = Organization.query.get(row['organization_id'])
                if organization:
                    account = Account(
                        name=row['name'],
                        organization_id=row['organization_id']
                    )
                    db.session.add(account)
                else:
                    print(f"Skipping Account {row['name']}: Organization with ID {row['organization_id']} not found.")
            db.session.commit()
            print("Seeded Accounts")

        # Seed Auth Codes
        if AuthCode.query.first() is None:
            df = pd.read_csv('seed/data/auth_codes.csv') # Corrected filename
            for _, row in df.iterrows():
                # Ensure account exists
                account = Account.query.get(row['account_id'])
                if account:
                    auth_code = AuthCode(
                        authcode=row['auth_code'], # Corrected column name
                        account_id=row['account_id'],
                        role=row['role'],
                        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24) # Always set default expiry
                    )
                    db.session.add(auth_code)
                else:
                    print(f"Skipping AuthCode {row['auth_code']}: Account with ID {row['account_id']} not found.")
            db.session.commit()
            print("Seeded Auth Codes")
            

        if ProjectTemplate.query.first() is  None:
            

            print("Seeding project templates from CSVs...")
            try:
                # 1. Seed Project Templates
                df_projects = pd.read_csv('seed/data/templates/project_templates.csv')
                for _, row in df_projects.iterrows():
                    project_template = ProjectTemplate(
                        id=row['id'],
                        name=row['name'],
                        description=row['description']
                    )
                    db.session.add(project_template)
                db.session.commit()
                print(f"Seeded {len(df_projects)} Project Templates")

                # 2. Seed Task Templates
                df_tasks = pd.read_csv('seed/data/templates/task_templates.csv')
                print("read seed/data/templates/task_templates.csv")
                # Replace blank parent_id with None (for SQLAlchemy)
                df_tasks['parent_id'] = df_tasks['parent_id'].astype('Int64').where(pd.notna(df_tasks['parent_id']), None)
                
                for _, row in df_tasks.iterrows():
                    # Handle duration for parent tasks (which may be blank in the CSV)
                    duration_days = row['duration_days'] if pd.notna(row['duration_days']) else 0
                    parent_id_value = row['parent_id'] if pd.notna(row['parent_id']) else None
                    task_template = TaskTemplate(
                        id=row['id'],
                        project_template_id=row['project_template_id'],
                        name=row['name'],
                        duration=int(duration_days * 86400), # Convert days to seconds
                        parent_id=parent_id_value
                    )
                    db.session.add(task_template)
                db.session.commit()
                print(f"Seeded {len(df_tasks)} Task Templates")

                # 3. Seed Dependencies
                df_deps = pd.read_csv('seed/data/templates/task_template_dependencies.csv')
                for _, row in df_deps.iterrows():
                    # Find the actual TaskTemplate objects
                    task = TaskTemplate.query.get(row['task_template_id'])
                    depends_on_task = TaskTemplate.query.get(row['depends_on_task_template_id'])
                    
                    if task and depends_on_task:
                        task.dependencies.append(depends_on_task)
                    else:
                        print(f"Warning: Could not create dependency for task_id {row['task_template_id']}. Task or dependency not found.")
                
                db.session.commit()
                print(f"Seeded {len(df_deps)} Template Dependencies")

            except FileNotFoundError as e:
                print(f"Error seeding templates: Could not find a template CSV file. {e}")
            except Exception as e:
                db.session.rollback()
                print(f"An error occurred during template seeding: {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Seed the database.')
    parser.add_argument('--delete', action='store_true', help='Delete all data before seeding.')
    args = parser.parse_args()
    seed_data(delete=args.delete)