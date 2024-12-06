from django.test import TestCase, Client
from django.contrib.auth.models import User 
from django.urls import reverse

# Create your tests here.

class LoginViewsTestCase(TestCase):
    def setUp(self):
        """Set up a test client & user"""
        self.client = Client()
        self.user = User.objects.create_user(username='user1', password='pass123')

    def test_get_request(self):
        """Test the GET request for the login view"""
        response = self.client.get(reverse('login')) # Make sure the URL works 
        self.assertEqual(response.status_code, 200) 
        self.assertTemplateUsed(response, 'templates/login_page.html')

    def test_post_request(self):
        """Test the POST request with valid login credentials"""
        response = self.client.post(reverse('login'), {'username': 'user2', 'password': 'password123'})
        
        # Need to add in a proper redirect here later 

    def test_post_invalid_user(self):
        """Test the POST request with invalid login credentials"""
        response = self.client.post(reverse('login'), {'username': 'user3', 'password': 'pass321'})
        self.assertTemplateUsed(response, 'templates/login.html')
        self.assertContains(response, 'Please enter a correct username and password.')
        