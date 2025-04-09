from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from admin_panel.models import Admin, FAQ, Tag, Log


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
        self.client.get(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)  # There should be no user id in the session


class FAQPageTestCase(TestCase):
    def setUp(self):
        """Set up a test client and FAQ objects"""
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='testpassword')

        self.faq_1 = FAQ.objects.create(question="When does the food bank open?",
                                        answer="The food bank is open Monday-Friday from 9:00 AM to 5:00 PM")
        self.faq_2 = FAQ.objects.create(question="How can I have access to the food bank client choice center?",
                                        answer="You must have an appointment.")
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
        self.assertContains(response, "You must have an appointment.")

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

    def test_add_valid_faq(self):
        """Test adding a valid FAQ"""
        faq_info = {
            'question': 'What do you sell?',
            'answer': 'We sell food of all kinds.',
            'existing_tags': [self.tag_1.id, self.tag_2.id],
            'new_tags': 'Products',
        }

        self.client.force_login(self.user)

        response = self.client.post(reverse('create_faq'), faq_info)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('faq_page'))

        faq = FAQ.objects.get(question='What do you sell?')
        self.assertIsNotNone(faq)
        self.assertEqual(faq.question, 'What do you sell?')
        self.assertEqual(faq.answer, 'We sell food of all kinds.')
        self.assertEqual(faq.tags.count(), 3)

    def test_add_invalid_faq(self):
        """Test adding an invalid FAQ"""
        faq_info = {
            'question': '',
            'answer': '',
            'existing_tags': [self.tag_1.id, self.tag_2.id],
            'new_tags': 'Products',
        }
        self.client.force_login(self.user)

        response = self.client.post(reverse('create_faq'), faq_info)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(FAQ.objects.filter(question='').exists())

    def test_edit_faq(self):
        """Test editing already existing FAQ"""
        self.client.force_login(self.user)
        faq = FAQ.objects.get(question="When does the food bank open?")
        new_faq_info = {
            'question': 'What do you sell?',
            'answer': 'We sell food of all kinds.',
            'existing_tags': [self.tag_1.id, self.tag_2.id],
            'new_tags': 'Products',
        }

        response = self.client.post(reverse('edit_faq', args=[faq.id]), new_faq_info)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('faq_page'))

        faq.refresh_from_db()

        self.assertEqual(faq.question, 'What do you sell?')
        self.assertEqual(faq.answer, 'We sell food of all kinds.')
        self.assertEqual(faq.tags.count(), 3)

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

class CreateAccountTests(TestCase):
    def setUp(self):
        self.client = Client()
        # set up a pre approved admin that is updated with username and password
        self.preapproved_admin = Admin.objects.create(foodbank_id="FB12345", foodbank_email="employee@foodbank.org", approved_for_admin_panel=True)
    
    def test_create_account_valid(self):
        """
        Test a valid admin account creation updates the preapproved record
        """
        url = reverse("create_account")
        data = {
            "username": "newadmin",
            "password": "newpassword", 
            "foodbank_employee_id": "FB12345",
            "foodbank_email": "employee@foodbank.org"
        }
        response = self.client.post(url, data, follow=True)
        self.assertEqual(response.status_code, 200)

        updated_admin = Admin.objects.get(foodbank_id="FB12345")
        self.assertEqual(updated_admin.username, "newadmin")
        self.assertNotEqual(updated_admin.password, data["password"]) # Make sure the password was hashed