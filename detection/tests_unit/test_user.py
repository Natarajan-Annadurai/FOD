from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User, Group
from detection.models import ProfileInformation, UserProfile
from detection.models import ServiceStation, Unit, Tray

class UserManagementTests(TestCase):

    def setUp(self):
        # Create admin user
        self.admin = User.objects.create_user(
            username="admin", password="password123"
        )
        self.admin_group = Group.objects.create(name="Admin")
        self.admin.groups.add(self.admin_group)

        # Login admin
        self.client.login(username="admin", password="password123")

        # URLs
        self.add_user_url = reverse("add_user")
        self.manage_users_url = reverse("manage_users")
        self.update_status_url = reverse("update_user_status")
        self.delete_user_url = lambda uid: reverse("delete_user", args=[uid])
        self.edit_user_url = reverse("edit_user")

    # -------------------------------------------------------------
    # 1. MANAGE USER PAGE ACCESS
    # -------------------------------------------------------------
    def test_manage_users_page_loads(self):
        response = self.client.get(self.manage_users_url)
        self.assertEqual(response.status_code, 200)

        # Check important UI parts
        self.assertContains(response, "<title>Manage Users", html=False)
        self.assertContains(response, "Manage Users & Roles")
        self.assertContains(response, "Add Users")
        self.assertContains(response, "Assigned Users")
        self.assertContains(response, "Dashboard")

    # -------------------------------------------------------------
    # 2. ADD USER
    # -------------------------------------------------------------
    def test_add_user_creates_new_user(self):
        data = {
            "username": "john",
            "email": "john@example.com",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!",
            "first_name": "John",
            "last_name": "Doe",
            "phone": "1234567890",
            "department": "IT",
            "location": "Chennai",
            "employee_id": "EMP001",
            "designation": "Engineer",
            "date_of_birth": "1990-01-01",
            "address": "Test Address",
            "gender": "Male",
            "role": self.admin_group.id,
            "status": "ACTIVE",
        }

        response = self.client.post(self.add_user_url, data)
        self.assertEqual(response.status_code, 302)

        new_user = User.objects.get(username="john")
        profile = ProfileInformation.objects.get(user=new_user)

        self.assertEqual(new_user.email, "john@example.com")
        self.assertEqual(profile.department, "IT")

    # -------------------------------------------------------------
    # 3. EDIT USER
    # -------------------------------------------------------------
    def test_edit_user_updates_profile(self):
        user = User.objects.create_user(username="jane", password="mypassword")
        ProfileInformation.objects.create(user=user)

        data = {
            "user_id": user.id,
            "email": "newmail@example.com",
            "first_name": "JaneNew",
            "last_name": "Doe",
            "password": "",
            "confirm_password": "",
            "phone": "9876543210",
            "department": "HR",
            "location": "Mumbai",
            "employee_id": "EMP002",
            "designation": "Manager",
            "date_of_birth": "1995-05-05",
            "address": "New Address",
            "gender": "Female",
            "status": "ACTIVE",
        }

        response = self.client.post(self.edit_user_url, data)
        self.assertEqual(response.status_code, 302)

        user.refresh_from_db()
        profile = ProfileInformation.objects.get(user=user)

        self.assertEqual(user.email, "newmail@example.com")
        self.assertEqual(profile.department, "HR")

    # -------------------------------------------------------------
    # 4. UPDATE USER STATUS
    # -------------------------------------------------------------
    def test_update_user_status(self):
        user = User.objects.create_user(username="dev", password="testpass")
        ProfileInformation.objects.create(user=user, status="ACTIVE")

        response = self.client.post(self.update_status_url, {
            "user_id": user.id,
            "status": "INACTIVE"
        })

        user.refresh_from_db()
        profile = ProfileInformation.objects.get(user=user)

        self.assertEqual(profile.status, "INACTIVE")

    # -------------------------------------------------------------
    # 5. DELETE USER
    # -------------------------------------------------------------
    def test_delete_user(self):
        user = User.objects.create_user(username="temp", password="temp")
        ProfileInformation.objects.create(user=user)

        response = self.client.get(self.delete_user_url(user.id))
        self.assertEqual(response.status_code, 302)

        with self.assertRaises(User.DoesNotExist):
            User.objects.get(username="temp")

    # -------------------------------------------------------------
    # 6. ROLE → GROUP SYNC TEST
    # -------------------------------------------------------------
    def test_role_sync_creates_or_updates_group(self):
        user = User.objects.create_user(username="sam", password="pass")
        ProfileInformation.objects.create(user=user)
        UserProfile.objects.create(user=user)

        station = ServiceStation.objects.create(name="Station1")
        unit = Unit.objects.create(name="Unit1", station=station)
        tray = Tray.objects.create(tray_name="Tray1", unit=unit)

        data = {
            "user_id": user.id,
            "role": "Supervisor",
            "stations": [station.id],
        }

        response = self.client.post(self.manage_users_url, data)

        user.refresh_from_db()
        self.assertTrue(user.groups.filter(name="Supervisor").exists())