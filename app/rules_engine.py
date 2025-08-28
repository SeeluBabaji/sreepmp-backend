from .models import *
from datetime import datetime, timedelta
from flask import current_app
import boto3
import os
import random
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError

def get_dashboard_content(user):
    """
    Determines the content to display on the user's dashboard based on their progress.
    """
    current_app.logger.info(f"Rules engine started for user: {user.email}")

    # Determine the problem category slug
    time_since_creation = datetime.utcnow() - user.created_at
    is_new_user = time_since_creation < timedelta(hours=1)
    current_app.logger.info(f"User is new: {is_new_user}")
    # user.current_problem_category_slug is null or new user
    
    projects_data = []
    # Build the base dashboard content
    dashboard_data = {
        'projects': 'none'
        
        }

   
    return dashboard_data

def get_test_content(user, spiral=False):
    """
    Determines the test content to display to the user.
    If spiral is True, it returns 20 random questions from modules with IDs less than the user's current_learning_focus_module_id.
    """
    if spiral:
        # Fetch all questions from modules with IDs less than current_learning_focus_module_id
        all_questions = TestQuestion.query.filter(
            TestQuestion.modules_id < user.current_learning_focus_module_id
        ).all()

        # Randomly select 20 questions
        if len(all_questions) > 20:
            questions = random.sample(all_questions, 20)
        else:
            questions = all_questions
    else:
        problem_category = ProblemCategory.query.filter_by(slug=user.current_problem_category_slug).first()
        if not problem_category:
            return []

        questions = TestQuestion.query.filter_by(
            problem_category_slug=problem_category.slug,
            modules_id=user.current_learning_focus_module_id
        ).all()

        if user.current_problem_category_slug == 'PSQ':
            last_test_attempt = UserTestAttempt.query.filter_by(user_id=user.id).order_by(UserTestAttempt.submitted_at.desc()).first()
            last_submitted_question_id = None
            if last_test_attempt:
                last_submitted_answer = UserTestAnswer.query.filter_by(
                    user_test_attempt_id=last_test_attempt.id
                ).order_by(UserTestAnswer.id.desc()).first()
                if last_submitted_answer:
                    last_submitted_question_id = last_submitted_answer.question_id
            
            if last_submitted_question_id:
                questions = [q for q in questions if q.id >= last_submitted_question_id] #return including the last question submitted so that if learning content is not watched yet, then we can cover that case.TODO eventually if the last submitted was correct answer, then we can skip that question and change >= to simply >.

    # Exclude 'correct_answer' from the response
    return questions

def _generate_presigned_s3_url(object_name, expiration=3600):
   """Generate a pre-signed URL to share an S3 object."""
   s3_bucket_name = os.environ.get("S3_BUCKET_NAME")
   if not s3_bucket_name:
       current_app.logger.error("S3_BUCKET_NAME environment variable not set.")
       return None

   s3_client = boto3.client('s3',
                            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                            region_name=os.environ.get("S3_REGION"))
   try:
       response = s3_client.generate_presigned_url('get_object',
                                                   Params={'Bucket': s3_bucket_name,
                                                           'Key': object_name},
                                                   ExpiresIn=expiration)
   except NoCredentialsError:
       current_app.logger.error("AWS credentials not found.")
       return None
   except PartialCredentialsError:
       current_app.logger.error("Incomplete AWS credentials.")
       return None
   except ClientError as e:
       current_app.logger.error(f"Could not generate presigned URL: {e}")
       return None
   return response

def _get_flutter_friendly_youtube_url(youtube_url):
   """
   Converts a standard YouTube URL to a Flutter-friendly embedded URL.
   """
   if "youtube.com/watch?v=" in youtube_url:
       video_id = youtube_url.split("v=")[1].split("&")[0]
       return f"https://www.youtube.com/embed/{video_id}"
   elif "youtu.be/" in youtube_url:
       video_id = youtube_url.split("youtu.be/")[1].split("?")[0]
       return f"https://www.youtube.com/embed/{video_id}"
   return youtube_url

def _generate_learning_content_recommendations(incorrect_questions):
   learning_content_recommendations = []
   
   firstcontentid = 0
   
   for q_id in incorrect_questions:
       content = LearningContent.query.filter_by(test_questions_id=q_id).first()
       if content:
           if firstcontentid == 0 :
               firstcontentid = content.id
           current_app.logger.debug(f"Learning content available: {content.content_title}, {content.content_URL}")
           
           content_url = content.content_URL
           # Check if it's a YouTube link
           if content_url and ("youtube.com/watch?v=" in content_url or "youtu.be/" in content_url):
               content_url = _get_flutter_friendly_youtube_url(content_url)
           elif content_url and "s3.amazonaws.com" in content_url:
               # Extract the object key from the S3 URL
               # Assuming URL format: https://<bucket-name>.s3.amazonaws.com/<object-key>
               try:
                   bucket_name_end_index = content_url.find(".s3.amazonaws.com/")
                   if bucket_name_end_index != -1:
                       object_key = content_url[bucket_name_end_index + len(".s3.amazonaws.com/"):]
                       presigned_url = _generate_presigned_s3_url(object_key)
                       if presigned_url:
                           content_url = presigned_url
                       else:
                           current_app.logger.warning(f"Failed to generate presigned URL for {content.content_URL}. Using original URL.")
                   else:
                       current_app.logger.warning(f"S3 URL format not recognized for {content.content_URL}. Using original URL.")
               except Exception as e:
                   current_app.logger.error(f"Error processing S3 URL {content.content_URL}: {e}")
           
           learning_content_recommendations.append({
               'id': content.id, # Add content ID
               'question_id': q_id,
               'title': content.content_title,
               'content_url': content_url
           })
   return learning_content_recommendations, firstcontentid

def submit_test(user, answers, db):
    """
    Handles the submission of a practice test.
    """
    score = 0
    total_questions = len(answers)
    results = []
    incorrect_questions = []

    new_test_attempt = UserTestAttempt(
        user_id=user.id,
        module_id=user.current_learning_focus_module_id
    )
    db.session.add(new_test_attempt)

    for answer in answers:
        question_id = answer.get('question_id')
        user_answer = answer.get('selected_answer')

        if not question_id or not user_answer:
            db.session.rollback()
            return {'message': 'Each answer must include "question_id" and "selected_answer".'}, 400

        question = TestQuestion.query.get(question_id)
        if not question:
            db.session.rollback()
            return {'message': f'Question with id {question_id} not found.'}, 404

        correct_answer_field = f'wrong_answer_{question.correct_answer}'
        correct_answer_value = getattr(question, correct_answer_field)
        is_correct = (correct_answer_value == user_answer)
        if is_correct:
            score += 1
        else:
            incorrect_questions.append(question_id)
        
        results.append({
            'question_id': question_id,
            'user_answer': user_answer,
            'correct_answer': correct_answer_value, # Store the actual correct answer string
            'is_correct': is_correct
        })

        new_answer = UserTestAnswer(
            question_id=question_id,
            submitted_answer=user_answer,
            is_correct=is_correct
        )
        new_test_attempt.answers.append(new_answer)

    score_percentage = (score / total_questions) * 100 if total_questions > 0 else 0

    learning_content_recommendations = []
    firstcontentid = 0

    if score_percentage < 100:
            learning_content_recommendations, firstcontentid = _generate_learning_content_recommendations(incorrect_questions)
    if user.current_problem_category_slug == 'PT':
        if score_percentage == 100 :
            user.current_problem_category_slug = 'PSQ'
        else :
            if firstcontentid >0 : # Check if firstcontenturl is not empty
                    user.next_recommended_lesson_id = firstcontentid

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving test attempt: {e}")
        return {'message': 'Failed to save test attempt.', 'error': str(e)}, 500

    return {
        'message': 'Practice test submitted successfully.',
        'total_questions': total_questions,
        'correct_answers': score,
        'score_percentage': score_percentage,
        'results': results,
        'learning_content': learning_content_recommendations,
        'current_problem_category_slug': user.current_problem_category_slug
    }, 200


def update_next_recommended_lesson(user, learning_content_id, db):
    """
    Updates the user's next_recommended_lesson_id with the provided learning_content_id.
    If learning_content_id is None, it sets next_recommended_lesson_id to None.
    """
    user.next_recommended_lesson_id = learning_content_id if learning_content_id is not None else None
    try:
        db.session.commit()
        current_app.logger.info(f"User {user.email} next_recommended_lesson_id updated to {learning_content_id}")
        return {'message': 'Next recommended lesson ID updated successfully.'}, 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating next_recommended_lesson_id for user {user.email}: {e}")
        return {'message': 'Failed to update next recommended lesson ID.', 'error': str(e)}, 500

def completed_learning(user, db):
    """
    Evaluates the user's current problem category slug after completing learning content.
    If the current problem category is 'PT', it updates it to 'PSQ'.
    """
    current_app.logger.info(f"User {user.email} completed_learning problem category slug-------."+user.current_problem_category_slug)
        
    if   user.current_problem_category_slug == 'PT':
            new_completed_module = UserCompletedModules(
                user_id=user.id,
                module_id=user.current_learning_focus_module_id,
                problem_category_slug=user.current_problem_category_slug
            )
            
            user.current_problem_category_slug = 'PSQ'
            user.next_recommended_lesson_id = None # Clear the recommended lesson after completing learning
            
            # Add entry to UserCompletedModules
           
            db.session.add(new_completed_module)

            try:
                db.session.commit()
                current_app.logger.info(f"User {user.email} problem category slug updated to PSQ after completing learning.")
                return {'message': 'Problem category updated successfully.'}, 200
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error updating problem category slug to PSQ for user {user.email}: {e}")
                return {'message': 'Failed to update problem category slug.', 'error': str(e)}, 500
    elif user.current_problem_category_slug == 'PSQ':
            new_completed_module = UserCompletedModules(
                user_id=user.id,
                module_id=user.current_learning_focus_module_id,
                problem_category_slug=user.current_problem_category_slug
            )
            modules_id=user.current_learning_focus_module_id
            modules_id  = modules_id +1 # expectng learning path modules ids to be in sequence, eventaully need to maintain meta data
            user.current_problem_category_slug = 'PT'
            user.current_learning_focus_module_id = modules_id
            user.next_recommended_lesson_id = None # should be none already but Clearing anyway

            # Add entry to UserCompletedModules
            
            db.session.add(new_completed_module)

            try:
                db.session.commit()
                current_app.logger.info(f"User {user.email} problem category slug updated to PT after completing feedback.")
                return {'message': 'Problem category updated successfully.'}, 200
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error updating problem category slug to PT for user {user.email}: {e}")
                return {'message': 'Failed to update problem category slug.', 'error': str(e)}, 500
    return {'message': 'No change needed for problem category.'}, 200
