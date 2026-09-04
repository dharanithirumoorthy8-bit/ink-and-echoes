import os
import unittest

from app import create_app
from models import User, db


class AdminAuthTests(unittest.TestCase):
    def setUp(self):
        os.environ['ADMIN_USERNAME'] = 'admin-keeper'
        os.environ['ADMIN_PASSWORD'] = 'very-secret-admin-password'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_admin_login_uses_separate_credentials(self):
        client = self.app.test_client()

        response = client.post('/login', data={
            'username': 'admin-keeper',
            'password': 'very-secret-admin-password',
        }, follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        admin_user = User.query.filter_by(username='admin-keeper').first()
        self.assertIsNotNone(admin_user)
        self.assertTrue(admin_user.is_admin)


if __name__ == '__main__':
    unittest.main()
