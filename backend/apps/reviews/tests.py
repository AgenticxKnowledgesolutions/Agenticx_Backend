from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from apps.reviews.models import Review

class ReviewTests(APITestCase):
    def setUp(self):
        self.list_create_url = reverse('reviews-list')
        self.user = User.objects.create_user(
            username='testadmin',
            email='testadmin@example.com',
            password='testpassword'
        )
        self.review1 = Review.objects.create(
            name="John Doe",
            rating=5,
            review="Excellent platform and mentorship!",
            role="AI Engineer",
            source="internal",
            is_active=True
        )
        self.review2 = Review.objects.create(
            name="Jane Smith",
            rating=4,
            review="Very structured courses.",
            role="Data Scientist",
            source="google",
            is_active=True
        )
        self.inactive_review = Review.objects.create(
            name="Inactive User",
            rating=5,
            review="Should not be visible.",
            role="Tester",
            source="internal",
            is_active=False
        )

    def test_list_reviews_public(self):
        response = self.client.get(self.list_create_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Results should be wrapped in pagination since it's enabled globally
        self.assertIn('results', response.data)
        
        # Only active reviews should be listed (review1 and review2)
        results = response.data['results']
        self.assertEqual(len(results), 2)
        
        # Sorted by rating (descending), then created_at (descending)
        # So John Doe (5 rating) should be first, then Jane Smith (4 rating)
        self.assertEqual(results[0]['name'], "John Doe")
        self.assertEqual(results[1]['name'], "Jane Smith")

    def test_create_review_unauthenticated_fails(self):
        data = {
            "name": "Bob Johnson",
            "rating": 5,
            "review": "Awesome experience!",
            "role": "Fullstack Developer",
            "source": "internal"
        }
        response = self.client.post(self.list_create_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_review_success(self):
        self.client.force_authenticate(user=self.user)
        data = {
            "name": "Bob Johnson",
            "rating": 5,
            "review": "Awesome experience!",
            "role": "Fullstack Developer",
            "source": "internal"
        }
        response = self.client.post(self.list_create_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Review.objects.count(), 4)
        new_review = Review.objects.get(name="Bob Johnson")
        self.assertEqual(new_review.rating, 5)
        self.assertEqual(new_review.is_active, True)  # Default value



