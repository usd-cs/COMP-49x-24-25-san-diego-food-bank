from django.test import TestCase, Client
from django.contrib.auth.models import User


class ViewsTestCase(TestCase):
    def setup(self):
        """
        Set up a test client and test user
        """
        self.client = Client()
        self.user = User.objects.create_user(username='user1', password='pass123')

    def test_login_view_get(self):
        """
        Test GET request for the login view
        """