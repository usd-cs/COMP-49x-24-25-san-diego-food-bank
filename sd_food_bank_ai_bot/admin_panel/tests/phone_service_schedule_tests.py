from django.test import TestCase, RequestFactory, Client
from admin_panel.views.phone_service_schedule import *
from unittest.mock import patch, MagicMock
import xml.etree.ElementTree as ET
from django.urls import reverse
from ..models import User


class RequestPhoneNumberTests(TestCase):
    def setUp(self):
        """Setup a request factory for use during tests"""
        self.factory = RequestFactory()
    
    def test_get_phone_number_US_valid(self):
        """Test getting the phone number the user is calling from in the US when it is valid"""
        phone_number = "+16192222222"
        
        request = self.factory.post("/answer/", {"From": f"{phone_number}"})
        response = get_phone_number(request)
        
        self.assertEqual(phone_number, response)

    def test_get_phone_number_MEX_valid(self):
        """Test getting the phone number the user is calling from in Mexico when it is valid"""
        phone_number = "+521212341234"

        request = self.factory.post("/answer/", {"From": f"{phone_number}"})
        response = get_phone_number(request)
        
        self.assertEqual(phone_number, response)

    def test_get_phone_number_invalid(self):
        """Test getting the phone number the user is calling from when it is invalid"""
        phone_number = "UNKNOWN"
        
        request = self.factory.post("/answer/", {"From": f"{phone_number}"})
        response = get_phone_number(request)

        self.assertEqual(None, response)


class PhoneSchedulingService(TestCase):
    def setUp(self):
        self.client = Client()
        self.test_user = User.objects.create(
            first_name="Billy",
            last_name="Bob",
            phone_number="+1234567890",
            email="billybob@email.com"
        )
    
    def test_check_account_found(self):
        """
        Test that when an account exists for the caller's number, the response
        contains their name and a confirmation.
        """
        response = self.client.post(
            reverse("check_account"),
            {"From": self.test_user.phone_number}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        root = ET.fromstring(content)
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)

        self.assertIn("Hello, Billy Bob", say_text)
        self.assertIn("Is this your account?", say_text)
    
    def test_check_account_not_found(self):
        """
        Test that when no account exists for the phone number, the response
        informs the caller.
        """
        response = self.client.post(
            reverse("check_account"),
            {"From": "+1987654321"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = ET.fromstring(content)
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("We did not find an account", say_text)
    
    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_confirm_account_yes(self, mock_get_response_sentiment):
        """
        Test that when the caller confirms by saying "yes", the response 
        will confirm the account.
        """
        mock_get_response_sentiment.return_value = True
        response = self.client.post(
            reverse("confirm_account"),
            {"SpeechResult": "Yes, that's correct"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = ET.fromstring(content)
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("Your account has been confirmed!", say_text)
    
    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_confirm_account_no(self, mock_get_response_sentiment):
        """
        Test that when the caller confirms by saying "no", the response 
        will encourage them to try again.
        """
        mock_get_response_sentiment.return_value = False
        response = self.client.post(
            reverse("confirm_account"),
            {"SpeechResult": "No, that's not right"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = ET.fromstring(content)
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("I'm sorry, please try again.", say_text)