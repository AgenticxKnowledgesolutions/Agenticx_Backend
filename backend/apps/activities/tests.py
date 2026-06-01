from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from apps.activities.models import Activity

class ActivityTests(APITestCase):
    def setUp(self):
        self.list_create_url = reverse('activity-list')
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpassword'
        )
        self.regular_user = User.objects.create_user(
            username='user',
            email='user@example.com',
            password='userpassword'
        )
        self.activity = Activity.objects.create(
            title="Introduction to AI",
            description="Learn the basics of AI.",
            duration="2 hours",
            price=150.00,
            is_free=False
        )

    def test_list_activities_public(self):
        response = self.client.get(self.list_create_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Results should be wrapped in pagination since we enabled it globally
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], "Introduction to AI")

    def test_create_activity_unauthenticated_fails(self):
        data = {
            "title": "New Workshop",
            "description": "An exciting workshop.",
            "duration": "1 day",
            "is_free": True
        }
        response = self.client.post(self.list_create_url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_activity_regular_user_fails(self):
        self.client.force_authenticate(user=self.regular_user)
        data = {
            "title": "New Workshop",
            "description": "An exciting workshop.",
            "duration": "1 day",
            "is_free": True
        }
        response = self.client.post(self.list_create_url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_activity_admin_success(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {
            "title": "Premium AI Workshop",
            "description": "A paid hands-on workshop.",
            "duration": "1 day",
            "price": 299.99,
            "is_free": False
        }
        response = self.client.post(self.list_create_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Activity.objects.count(), 2)

    def test_create_activity_validation_free_with_price(self):
        self.client.force_authenticate(user=self.admin_user)
        # Free activity with positive price should fail validation
        data = {
            "title": "Free Workshop",
            "description": "No cost.",
            "duration": "1 day",
            "price": 10.00,
            "is_free": True
        }
        response = self.client.post(self.list_create_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('price', response.data)

    def test_create_activity_validation_paid_without_price(self):
        self.client.force_authenticate(user=self.admin_user)
        # Paid activity with null/missing price should fail validation
        data = {
            "title": "Paid Workshop",
            "description": "Premium content.",
            "duration": "1 day",
            "is_free": False
        }
        response = self.client.post(self.list_create_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('price', response.data)
