from django.test import TestCase, Client
from admin_panel.models import Admin, Log
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from zoneinfo import ZoneInfo


class MainPageTests(TestCase):
    def setUp(self):
        """Set up a test client, admin, and logs"""
        self.client = Client()
        self.admin = Admin.objects.create_user(username='user1',
                                            password='pass123')
        
        pst = ZoneInfo("America/Los_Angeles")
        self.log_starts = timezone.now().astimezone(pst)
        self.log_1 = Log.objects.create(
            phone_number="+16191231234",
            time_started = self.log_starts,
            length_of_call = timedelta(minutes=10)
        )

        self.log_2 = Log.objects.create(
            phone_number="+16193214321",
            time_started = self.log_starts,
            length_of_call = timedelta(minutes=7)
        )
            
    def test_get_request(self):
        """Test the GET request for Audit Logs view"""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('audit_logs'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'audit_logs.html')

    def test_logs_displayed(self):
        """Test all items being displayed when not searching"""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('audit_logs'))

        day = self.log_starts.strftime("%b %d, %Y")

        # Check first log appears
        self.assertContains(response, "+16191231234")
        self.assertContains(response, day)
        self.assertContains(response, timedelta(minutes=10))

        # Check second log appears
        self.assertContains(response, "+16193214321")
        self.assertContains(response, day)
        self.assertContains(response, timedelta(minutes=7))
    
    def test_search_no_results(self):
        """Test no search results when searching for a phone number that does not have a log"""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('audit_logs'), {'q': "+1231231234"})
        
        self.assertNotContains(response, "+16191231234")
        self.assertNotContains(response, "+16193214321")
        self.assertContains(response, "No matching entries found")

    def test_search_with_results(self):
        """Test the correct item is displayed when searching for a phone number that has a log"""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('audit_logs'), {'q': "+16191231234"})
        
        self.assertContains(response, "+16191231234")
        self.assertNotContains(response, "+16193214321")
        self.assertNotContains(response, "No matching entries found")