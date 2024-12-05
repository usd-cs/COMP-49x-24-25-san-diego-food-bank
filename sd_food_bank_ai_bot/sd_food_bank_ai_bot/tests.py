from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

class ViewsTestVase(TestCase):
    def setup(self):
        """
        Setup a test client and a test user
        """
        self.client = Client()
        self.user = User.objects.create_user(username='user1', password='pass123')

    def test_login_view_get(self):
        """
        Test GET request for login view
        """

        # Ensures URL patterns are properly defined 
        response = self.client.get(reverse('login')) 
        self.assertEqual(response.status_code, 200)