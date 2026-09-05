import os
import unittest
from datetime import date

from app import create_app
from models import User, Poem, db


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

    def test_default_admin_credentials_work_when_env_is_unset(self):
        db.session.query(User).delete()
        db.session.commit()

        for key in ['ADMIN_USERNAME', 'ADMIN_PASSWORD']:
            os.environ.pop(key, None)

        client = self.app.test_client()
        response = client.post('/login', data={
            'username': 'admin',
            'password': 'admin123',
        }, follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        admin_user = User.query.filter_by(username='admin').first()
        self.assertIsNotNone(admin_user)
        self.assertTrue(admin_user.is_admin)

    def test_signup_rejects_existing_user_and_logged_in_user_is_redirected(self):
        client = self.app.test_client()

        user = User(username='existing-user', email='existing@example.com', dob=date(2000, 1, 1))
        user.set_password('secretpass')
        db.session.add(user)
        db.session.commit()

        response = client.post('/signup', data={
            'username': 'existing-user',
            'email': 'existing@example.com',
            'password': 'newpass',
            'dob': '2000-01-01',
        }, follow_redirects=False)
        self.assertEqual(response.status_code, 302)

        login_response = client.post('/login', data={
            'username': 'existing-user',
            'password': 'secretpass',
        }, follow_redirects=False)
        self.assertEqual(login_response.status_code, 302)

        redirected = client.get('/signup', follow_redirects=False)
        self.assertEqual(redirected.status_code, 302)

    def test_admin_poem_upload_is_one_time_only_and_full_poem_is_visible(self):
        client = self.app.test_client()
        login_response = client.post('/login', data={
            'username': 'admin-keeper',
            'password': 'very-secret-admin-password',
        }, follow_redirects=False)
        self.assertEqual(login_response.status_code, 302)

        poem_payload = {
            'title': 'Echoes of Dawn',
            'category': 'love,grief',
            'body': 'I carry the morning like a lantern in my hands.'
        }

        first_upload = client.post('/admin/poem/new', data=poem_payload, follow_redirects=False)
        self.assertEqual(first_upload.status_code, 302)
        self.assertEqual(Poem.query.filter_by(title='Echoes of Dawn').count(), 1)

        duplicate_upload = client.post('/admin/poem/new', data=poem_payload, follow_redirects=False)
        self.assertEqual(duplicate_upload.status_code, 302)
        self.assertEqual(Poem.query.filter_by(title='Echoes of Dawn').count(), 1)

        poem_page = client.get('/poems', follow_redirects=True)
        self.assertIn('I carry the morning like a lantern in my hands.', poem_page.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
