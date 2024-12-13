from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from admin_panel.models import Admin, FAQ, Tag


class LoginViewsTestCase(TestCase):
    def setUp(self):
        """Set up a test client & user"""
        self.client = Client()
        self.admin = Admin.objects.create_user(username='user1', password='pass123')

    def test_get_request(self):
        """Test the GET request for the login view"""
        response = self.client.get(reverse('login'))  # Make sure the URL works
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


class LogoutViewTestCase(TestCase):
    def setUp(self):
        """Set up test client and a user"""
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='testpassword')

    def test_logout_redirect(self):
        """Test that the logout view redirects back to login page"""
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('login'))

    def test_user_logged_out(self):
        """Test to make sure the user is logged out"""
        self.client.login(username='testuser', password='testpassword')
        self.assertNotIn('_auth_user_id', self.client.session)  # There should be no user id in the session


class FAQPageTestCase(TestCase):
    def setUp(self):
        """Set up a test client and FAQ objects"""
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='testpassword')

        self.faq_1 = FAQ.objects.create(question="When does the food bank open?", answer="The food bank is open Monday-Friday from 9:00 AM to 5:00 PM")
        self.faq_2 = FAQ.objects.create(question="How can I have access to the food bank client choice center?", answer="To have access to the client choice center, you must have scheduled an appointment")
        self.tag_1 = Tag.objects.create(name="Hours")
        self.tag_2 = Tag.objects.create(name="Access")
        self.faq_1.tags.add(self.tag_1)
        self.faq_2.tags.add(self.tag_2)

    def test_get_request(self):
        """Test the GET request for FAQ view"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('faq_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'faq_page.html')

    def test_items_displayed(self):
        """Test all items being displayed when not searching"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('faq_page'))

        # Check first FAQ appears
        self.assertContains(response, "When does the food bank open?")
        self.assertContains(response, "The food bank is open Monday-Friday from 9:00 AM to 5:00 PM")

        # Check second FAQ appears
        self.assertContains(response, "How can I have access to the food bank client choice center?")
        self.assertContains(response, "To have access to the client choice center, you must have scheduled an appointment")

    def test_delete_faq(self):
        """Test deleting an FAQ"""
        # Verify the FAQ exists initially
        self.assertTrue(FAQ.objects.filter(id=self.faq_1.id).exists())

        # Send POST request to delete the FAQ
        self.client.force_login(self.user)
        response = self.client.post(reverse('delete_faq', args=[self.faq_1.id]))

        # Check redirection after deletion
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('faq_page'))

        # Verify the FAQ no longer exists in the database
        self.assertFalse(FAQ.objects.filter(id=self.faq_1.id).exists())

        # Check if the FAQ is no longer displayed on the page
        response = self.client.get(reverse('faq_page'))
        self.assertNotContains(response, "When does the food bank open?")
        self.assertNotContains(response, "The food bank is open Monday-Friday from 9:00 AM to 5:00 PM")

    def test_search_no_results(self):
        """Test no search results when searching for a string not in any questions/answers"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('faq_page'), {'q': "asdfasdfasdfasdf"})
        self.assertNotContains(response, "When does the food bank open?")
        self.assertNotContains(response, "How can I have access to the food bank client choice center?")
        self.assertContains(response, "No matching entries found")

    def test_search_with_results(self):
        """Test the correct item is displayed when searching for a string in a question/answer"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('faq_page'), {'q': "appointment"})
        self.assertContains(response, "How can I have access to the food bank client choice center?")
        self.assertNotContains(response, "When does the food bank open?")

    def test_tag_filter_hours(self):
        """Test filtering by 'Hours' tag"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('faq_page'), {'tag': self.tag_1.id})
        self.assertContains(response, "When does the food bank open?")
        self.assertNotContains(response, "How can I have access to the food bank client choice center?")

    def test_tag_filter_access(self):
        """Test filtering by 'Access' tag"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('faq_page'), {'tag': self.tag_2.id})
        self.assertContains(response, "How can I have access to the food bank client choice center?")
        self.assertNotContains(response, "When does the food bank open?")

    def test_tag_filter_all_tags(self):
        """Test displaying all FAQs when no tag is selected"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('faq_page'))
        self.assertContains(response, "When does the food bank open?")
        self.assertContains(response, "How can I have access to the food bank client choice center?")
