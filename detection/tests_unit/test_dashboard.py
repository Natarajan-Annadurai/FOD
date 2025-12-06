from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group

class DashboardViewTests(TestCase):
    def setUp(self):
        # Create a test user
        self.username = "testuser"
        self.password = "testpassword123"
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.client = Client()
        self.dashboard_url = reverse('dashboard')  # Change 'dashboard' to your URL name

    def test_dashboard_page_loads_for_authenticated_user(self):
        # Login first
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')  # replace with your template name
        # Check that user's username is in the response
        self.assertContains(response, self.username)

    def test_dashboard_redirects_for_anonymous_user(self):
        response = self.client.get(self.dashboard_url)
        # Should redirect to login page
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_dashboard_contains_main_cards(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.dashboard_url)
        self.assertContains(response, "Analytics & Information Board")
        self.assertContains(response, "Centralized Management System")
        self.assertContains(response, "Tool Creation")
        self.assertContains(response, "Tool Assignment")
        self.assertContains(response, "Inventory Management")
        self.assertContains(response, "Service Station Management")
        self.assertContains(response, "User Management")
        self.assertContains(response, "Aircraft Management")
        self.assertContains(response, "Job Card Management")

    def test_dashboard_contains_main_cards_url_check(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.dashboard_url)

        cards = {
            "Analytics & Information Board": 'tool_activity_dashboard',
            "Centralized Management System": 'centralized_system_monitoring',
            "Tool Creation": 'tool_creation',
            "Tool Assignment": 'global_assigned_tools',
            "Inventory Management": 'inventory',
            "Service Station Management": 'service_station_list',
            "User Management": 'manage_users',
            "Aircraft Management": 'aircraft_list',
            "Job Card Management": 'jobcard_list',
        }

        for card_text, url_name in cards.items():
            # Check the card exists in the dashboard
            self.assertContains(response, card_text)

            # Simulate clicking the card by sending a GET request to its URL
            card_url = reverse(url_name)
            card_response = self.client.get(card_url)
            self.assertEqual(card_response.status_code, 200)