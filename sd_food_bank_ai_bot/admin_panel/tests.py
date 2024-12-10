from django.test import TestCase, Client
from django.contrib.auth.models import User 
from django.urls import reverse
from admin_panel.models import Admin, FAQ


class LoginViewsTestCase(TestCase):
    def setUp(self):
        """Set up a test client & user"""
        self.client = Client()
        self.admin = Admin.objects.create_user(username='user1', password='pass123')

    def test_get_request(self):
        """Test the GET request for the login view"""
        response = self.client.get(reverse('login')) # Make sure the URL works 
        self.assertEqual(response.status_code, 200) 
        self.assertTemplateUsed(response, 'login.html')

    def test_post_request(self):
        """Test the POST request with valid login credentials"""
        response = self.client.post(reverse('login'), {'username': 'user1', 'password': 'pass123'})
        self.assertEqual(response.status_code, 302)

    def test_post_invalid_user(self):
        """Test the POST request with invalid login credentials"""
        response = self.client.post(reverse('login'), {'username': 'user3', 'password': 'pass321'})
        self.assertTemplateUsed(response, 'login.html')


class FAQPageTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.faq_1 = FAQ.objects.create(question="When does the food bank open?", answer="The food bank is open Monday-Friday from ():00 AM to 5:00 PM")
        self.faq_2 = FAQ.objects.create(question="How can I have access to the food bank client choice center?", answer="To have access to the client choice center, you must have scheduled an appointment")
    
    def test_get_request(self):
        """Test the GET request for FAQ view"""
        response = self.client.get(reverse('faq_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'faq_page.html')
    
    def test_items_displayed(self):
        response = self.client.get(reverse('faq_page'))

        # Check first FAQ appears
        self.assertContains(response, "When does the food bank open?")
        self.assertContains(response, "The food bank is open Monday-Friday from ():00 AM to 5:00 PM")

        # Check second FAQ appears
        self.assertContains(response, "How can I have access to the food bank client choice center?")
        self.assertContains(response, "To have access to the client choice center, you must have scheduled an appointment")

    
        