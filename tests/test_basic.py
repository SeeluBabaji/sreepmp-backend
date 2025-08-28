import unittest
from unittest.mock import patch
from app import create_app, db
from app.models import User, Module, ProblemCategory, Concept, TestQuestion

#python -m unittest discover tests.  

class BasicTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        # Note: We don't need to create a user with a password anymore,
        # as the Google auth mock will handle user creation.

        # Add a module, problem category, and concept for testing
        module = Module(name='Test Module')
        problem_category = ProblemCategory(slug='test-category', name='Test Category')
        concept1 = Concept(name='Test Concept 1', modules_id=module.id)
        concept2 = Concept(name='Test Concept 2', modules_id=module.id)
        db.session.add_all([module, problem_category, concept1, concept2])
        db.session.commit()

        # Add a test question
        question = TestQuestion(
            question_text='This is a test question',
            correct_answer='A',
            wrong_answer_1='B',
            wrong_answer_2='C',
            wrong_answer_3='D',
            wrong_answer_4='E',
            modules_id=module.id,
            concepts_id=concept2.id,
            problem_category_slug=problem_category.slug
        )
        db.session.add(question)
        db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_health_check(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode(), 'API is healthy!')

    @patch('app.google_auth_service.GoogleAuthService.verify_token')
    def _get_google_auth_token(self, mock_verify_token):
        # Configure the mock to return a specific user email
        mock_verify_token.return_value = {'email': 'test@example.com'}

        # Make the request to the Google auth endpoint
        response = self.client.post(
            '/api/v1/auth/google',
            json={'token': 'fake-google-token'}
        )
        self.assertEqual(response.status_code, 200)
        json_response = response.get_json()
        self.assertIn('token', json_response)
        return json_response['token']

    def test_google_login(self):
        """Test that we can get a token via the Google auth endpoint."""
        token = self._get_google_auth_token()
        self.assertIsNotNone(token)

    def test_get_test_questions(self):
        """Test fetching questions using a token from Google auth."""
        token = self._get_google_auth_token()

        # Use the token to access the protected route
        response = self.client.get(
            '/api/v1/test_questions',
            headers={'Authorization': f'Bearer {token}'}
        )
        self.assertEqual(response.status_code, 200)
        json_response = response.get_json()
        self.assertIn('questions', json_response)

    def test_get_test_questions_with_filter(self):
        """Test fetching and filtering questions using a token from Google auth."""
        token = self._get_google_auth_token()

        # Use the token to access the protected route with a filter
        response = self.client.get(
            '/api/v1/test_questions?concepts_id=2',
            headers={'Authorization': f'Bearer {token}'}
        )
        self.assertEqual(response.status_code, 200)
        json_response = response.get_json()
        self.assertIn('questions', json_response)
        # Add more assertions here to verify the filtering logic
        for question in json_response['questions']:
            self.assertEqual(2, question['concepts_id'])
if __name__ == '__main__':
    unittest.main()