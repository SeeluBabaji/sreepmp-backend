import argparse
from app import create_app, db
from app.models import User, Concept, UserTestAttempt, UserTestAnswer, UserCompletedModules

def delete_data(model_name, model_id):
    """Deletes a specific model instance and its related data."""
    app = create_app()
    with app.app_context():
        if model_name.lower() == 'user':
            user = db.session.get(User, model_id)
            if user:
                # Create a subquery for the attempt IDs to avoid loading them all
                attempt_ids_subquery = db.session.query(UserTestAttempt.id).filter_by(user_id=user.id).scalar_subquery()

                # Delete answers associated with those attempts
                UserTestAnswer.query.filter(UserTestAnswer.user_test_attempt_id.in_(attempt_ids_subquery)).delete(synchronize_session=False)

                # Delete the attempts themselves
                UserTestAttempt.query.filter_by(user_id=user.id).delete(synchronize_session=False)
                
                # Delete the UserCompletedModules 
                UserCompletedModules.query.filter_by(user_id=user.id).delete(synchronize_session=False)
                
                # Now delete the user
                db.session.delete(user)
                db.session.commit()
                print(f"User with ID {model_id} and related data has been deleted.")
            else:
                print(f"User with ID {model_id} not found.")
        elif model_name.lower() == 'concept':
            concept = db.session.get(Concept, model_id)
            if concept:
                db.session.delete(concept)
                db.session.commit()
                print(f"Concept with ID {model_id} has been deleted.")
            else:
                print(f"Concept with ID {model_id} not found.")
        else:
            print(f"Model '{model_name}' is not supported for deletion.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Delete a specific model instance from the database.')
    parser.add_argument('model_name', type=str, help='The name of the model to delete (e.g., "user", "concept").')
    parser.add_argument('model_id', type=int, help='The ID of the model instance to delete.')
    args = parser.parse_args()
    delete_data(args.model_name, args.model_id)