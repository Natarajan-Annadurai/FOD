from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import reverse
from detection.views import LOCKOUT_TIME

class LoginPageTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.username = "testuser"
        self.password = "TestPass123"
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.login_url = reverse('login')
        self.dashboard_url = reverse('dashboard')

    def tearDown(self):
        cache.clear()  # clear cache after each test

    def test_login_page_loads(self):
        """Login page should load successfully"""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User Login")

    def test_successful_login_redirects_dashboard(self):
        """User with correct credentials should be redirected to dashboard"""
        response = self.client.post(self.login_url, {'username': self.username, 'password': self.password})
        self.assertRedirects(response, self.dashboard_url)

    def test_failed_login_shows_error_message(self):
        """Invalid credentials should show error message"""
        response = self.client.post(self.login_url, {'username': self.username, 'password': 'wrongpass'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid login")

    def test_account_lockout_after_max_attempts(self):
        """Account should lock after 3 failed login attempts"""
        for i in range(3):
            self.client.post(self.login_url, {'username': self.username, 'password': 'wrongpass'})
        # 4th attempt should be locked
        response = self.client.post(self.login_url, {'username': self.username, 'password': 'wrongpass'})
        self.assertContains(response, "Account locked. Try again")

    def test_login_after_lockout_expires(self):
        """User should be able to login after lockout expires"""
        import time
        for i in range(3):
            self.client.post(self.login_url, {'username': self.username, 'password': 'wrongpass'})
        time.sleep(LOCKOUT_TIME + 1)
        response = self.client.post(self.login_url, {'username': self.username, 'password': self.password})
        self.assertRedirects(response, self.dashboard_url)