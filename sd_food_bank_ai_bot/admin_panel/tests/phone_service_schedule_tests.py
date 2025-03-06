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
    
class SchedulingServiceTests(TestCase):
    def setUp(self):
        self.client = Client()

    def parse_twiML(self, content):
        """
        Helper method to parse TwiML response and convert it into an XML element tree.

        This allows some of our tests to only focus on validating the response and not have to 
        repeat the parsing logic for the TwiML responses.
        """
        return ET.fromstring(content)
    
    def test_schedule_nearest_available(self):
        """
        Test that the schedule_nearest_available endpoint will return 
        a 'Gather' with the expected appointment prompt.
        """
        response = self.client.get(reverse("schedule_nearest_available"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = self.parse_twiML(content)
        
        # Check that there is at least one 'Gather' element with a prompt that mentions "available appointment"
        gathers = list(root.iter("Gather"))
        self.assertTrue(len(gathers) > 0, "No <Gather> element found.")
        gather_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("The nearest available appointment is at", gather_text)

    def test_handle_schedule_response_yes(self):
        """
        Test that when the caller confirms with "yes", the response confirms the appointment and hangs up.
        """
        response = self.client.post(
            reverse("handle_schedule_response"),
            {"SpeechResult": "Yes, please"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = self.parse_twiML(content)
        
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("Your appointment has been scheduled!", say_text)

    def test_handle_schedule_response_no(self):
        """
        Test that when the caller says 'no', the response prompts for further options.
        """
        response = self.client.post(
            reverse("handle_schedule_response"),
            {"SpeechResult": "No"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = self.parse_twiML(content)
        
        # Check that the response contains the prompt asking if they'd like to hear other times or choose a different date.
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("Would you like to hear other available times", say_text)
        # Ensure a Gather element is present for the next step.
        gathers = list(root.iter("Gather"))
        self.assertTrue(len(gathers) > 0, "No <Gather> element found in response for 'no' response.")

    def test_handle_schedule_options_other_times(self):
        """
        Test that when the caller says "other times", the system offers an alternative slot.
        """
        response = self.client.post(
            reverse("handle_schedule_options"),
            {"SpeechResult": "other times"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = self.parse_twiML(content)
        
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("Another available appointment is at", say_text)
    
        gathers = list(root.iter("Gather"))
        self.assertTrue(len(gathers) > 0, "Expected a <Gather> element for alternative times.")

    def test_handle_schedule_options_different_date(self):
        """
        Test that when the caller says "different date", the system prompts for a date.
        """
        response = self.client.post(
            reverse("handle_schedule_options"),
            {"SpeechResult": "different date"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = self.parse_twiML(content)
        
        # There should be a Gather element prompting the caller for a date.
        gathers = list(root.iter("Gather"))
        self.assertTrue(len(gathers) > 0, "Expected a <Gather> element for date input.")
        gather_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("What date would you like to schedule an appointment for?", gather_text)
    
    def test_handle_schedule_options_unknown(self):
        """
        Test that when the caller's next response is unrecognized, the response will apologize and redirect.
        """
        response = self.client.post(
            reverse("handle_schedule_options"),
            {"SpeechResult": "I don't know"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = self.parse_twiML(content)
        
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("I'm sorry, I didn't understand that", say_text)
        redirect_elem = root.find("Redirect")
        self.assertIsNotNone(redirect_elem, "Expected a <Redirect> element when input is unrecognized.")

    def test_handle_date_input(self):
        """
        Test that when the caller provides a date, the system offers an appointment slot for that day.
        """
        # Simulate the caller says "March 10th" as the next date.
        response = self.client.post(
            reverse("handle_date_input"),
            {"SpeechResult": "March 10th"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = self.parse_twiML(content)
        
        # Check that the prompt includes the provided date and the simulated slot "4:00 PM".
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("March 10th", say_text)
        self.assertIn("4:00 PM", say_text)
        
        gathers = list(root.iter("Gather"))
        self.assertTrue(len(gathers) > 0, "Expected a <Gather> element for confirming the appointment on the provided date.")