from django.test import TestCase, RequestFactory, Client
from admin_panel.views.phone_service_schedule import *
from unittest.mock import patch, MagicMock
import xml.etree.ElementTree as ET
from django.urls import reverse
from django.utils.timezone import now
from datetime import timedelta, time
from ..models import User, AppointmentTable
import urllib.parse


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
        prompts the user for their name.
        """
        response = self.client.post(
            reverse("check_account"),
            {"From": "+1987654321"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = ET.fromstring(content)
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("Can I get your first and last name please?", say_text)
    
    @patch("admin_panel.views.phone_service_schedule.get_phone_number")
    def test_check_account_invalid_phone(self, mock_get_phone_number):
        """
        Test proper response when an invalid phone number is returned
        """
        mock_get_phone_number.return_value = None
        response = self.client.post(
            reverse("check_account"),
            {"From": "+1987654321"}
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = ET.fromstring(content)
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("Sorry, we are unable to help you at this time.", say_text)
    
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
<<<<<<< HEAD
    
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
        self.assertIn("Our nearest appointment slot is 3:15 PM. Does that work for you?", gather_text)

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
        self.assertIn("Another available appointment is available at 3:45 PM. Would you like to schedule this appointment? Please say yes or no.", say_text)
    
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
=======

class NameRequestTests(TestCase):
    def setUp(self):
        """Setup a request factory for use during tests"""
        self.factory = RequestFactory()
    
    @patch("admin_panel.views.phone_service_schedule.OpenAI")
    def test_get_name_valid(self, mock_openai):
        """Test get_name when there is a valid input"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Billy Bob"))]
        )

        request = self.factory.post("/get_name/", {"SpeechResult": "My name is Billy Bob"})
        response = get_name(request)

        self.assertIn("Your name is Billy Bob. Is that correct?", response.content.decode())
    
    @patch("admin_panel.views.phone_service_schedule.OpenAI")
    def test_get_name_invalid(self, mock_openai):
        """Test get_name when there is no SpeechResult"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Billy Bob"))]
        )

        request = self.factory.post("/get_name/", {"SpeechResult": ""})
        response = get_name(request)

        mock_openai.assert_not_called()
        self.assertIn("/check_account/", response.content.decode())
    
    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_process_name_confirmation_valid(self, mock_get_response_sentiment):
        """Test all valid data with only first and last name"""
        mock_get_response_sentiment.return_value = True
        
        name = "Billy Bob"
        name_encoded = urllib.parse.quote(name)
        request = self.factory.post(f"/process_name_confirmation/{name_encoded}/", {"From": "+16294968157"})
        response = process_name_confirmation(request, name_encoded)

        self.assertTrue(User.objects.filter(phone_number="+16294968157").exists())
        self.assertIn("Rerouting to get date.", response.content.decode())
    
    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_process_name_confirmation_valid_with_middle(self, mock_get_response_sentiment):
        """Test all valid data with first, middle, and last name"""
        mock_get_response_sentiment.return_value = True
        
        name = "Billy Joseph Bob"
        name_encoded = urllib.parse.quote(name)
        request = self.factory.post(f"/process_name_confirmation/{name_encoded}/", {"From": "+16294968156"})
        response = process_name_confirmation(request, name_encoded)

        self.assertTrue(User.objects.filter(phone_number="+16294968156", first_name="Billy", last_name="Bob").exists())
        self.assertIn("Rerouting to get date.", response.content.decode())
    

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_process_name_confirmation_valid_with_no_last(self, mock_get_response_sentiment):
        """Test all valid data with no last name"""
        mock_get_response_sentiment.return_value = True
        
        name = "Billy"
        name_encoded = urllib.parse.quote(name)
        request = self.factory.post(f"/process_name_confirmation/{name_encoded}/", {"From": "+16294968155"})
        response = process_name_confirmation(request, name_encoded)

        self.assertTrue(User.objects.filter(phone_number="+16294968155", first_name="Billy").exists())
        self.assertIn("Rerouting to get date.", response.content.decode())
    
    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_process_name_confirmation_invalid(self, mock_get_response_sentiment):
        """Test for when the user indicates that the correct name was not said"""
        mock_get_response_sentiment.return_value = False
        
        name = "Billy Bob"
        name_encoded = urllib.parse.quote(name)
        request = self.factory.post(f"/process_name_confirmation/{name_encoded}/", {"From": "+16294968156"})
        response = process_name_confirmation(request, name_encoded)

        self.assertFalse(User.objects.filter(phone_number="+16294968156").exists())
        self.assertIn("I'm sorry, please try again.", response.content.decode())
        self.assertIn("check_account", response.content.decode())

class AppointmentTests(TestCase):
    def setUp(self):
        """Set up test data for checking available appointments"""
        self.client = Client()
        self.today = now().date()
        self.target_weekday = 1 # Gets Tuesday
        self.url = reverse('check_for_appointment')  # Ensure this matches your URL patterns

        # Define business hours
        self.EARLIEST_TIME = time(9, 0)
        self.LATEST_TIME = time(17, 0)

        # Generate appointment dates for the next 4 weeks on Tuesday
        self.appointment_dates = [
            self.today + timedelta(days=(self.target_weekday - self.today.weekday()) % 7 + (week * 7)) for week in range(4)
        ]

    def test_check_for_appointment_valid_day(self):
        """Tests if check_for_appointment correctly identifies available days"""
        response = self.client.post(self.url, {'SpeechResult': 'Tuesday'})
        self.assertEqual(response.status_code, 200)
        self.assertIn("The next available Tuesday", str(response.content))

    def test_check_for_appointment_invalid_day(self):
        """Tests if check_for_appointment correctly handles an invalid day"""
        response = self.client.post(self.url, {'SpeechResult': 'Blursday'})  # Invalid day
        self.assertEqual(response.status_code, 200)
        self.assertIn("I did not recognize that day", str(response.content))

    def test_check_available_date_with_no_appointments(self):
        """Tests check_available_date when no appointments exist (should be fully open)"""
        is_available, appointment_date, num_available = check_available_date(self.target_weekday)
        self.assertTrue(is_available)
        self.assertEqual(num_available, 4)  # Default 4 slots

    def test_check_available_date_with_full_schedule(self):
        """Tests check_available_date when all slots are taken"""
        # Fill the whole day with back-to-back appointments
        for date in self.appointment_dates:
            AppointmentTable.objects.create(userID=1, appointmentID=101, start_time=self.EARLIEST_TIME, end_time=time(10, 0), location="Office", date=date)
            AppointmentTable.objects.create(userID=2, appointmentID=102, start_time=time(10, 0), end_time=time(11, 0), location="Office", date=date)
            AppointmentTable.objects.create(userID=3, appointmentID=103, start_time=time(11, 0), end_time=time(12, 0), location="Office", date=date)
            AppointmentTable.objects.create(userID=4, appointmentID=104, start_time=time(12, 0), end_time=time(13, 0), location="Office", date=date)
            AppointmentTable.objects.create(userID=5, appointmentID=105, start_time=time(13, 0), end_time=time(14, 0), location="Office", date=date)
            AppointmentTable.objects.create(userID=6, appointmentID=106, start_time=time(14, 0), end_time=time(15, 0), location="Office", date=date)
            AppointmentTable.objects.create(userID=7, appointmentID=107, start_time=time(15, 0), end_time=time(16, 0), location="Office", date=date)
            AppointmentTable.objects.create(userID=8, appointmentID=108, start_time=time(16, 0), end_time=self.LATEST_TIME, location="Office", date=date)

        is_available, appointment_date, num_available = check_available_date(self.target_weekday)
        self.assertFalse(is_available)
        self.assertIsNone(appointment_date)
        self.assertEqual(num_available, 0)

    def test_check_available_date_with_partial_availability(self):
        """Tests check_available_date when there are some open slots"""
        # Create some appointments but leave gaps
        AppointmentTable.objects.create(userID=1, appointmentID=101, start_time=self.EARLIEST_TIME, end_time=time(10, 0), location="Office", date=self.appointment_dates[0])
        AppointmentTable.objects.create(userID=2, appointmentID=102, start_time=time(12, 0), end_time=time(13, 0), location="Office", date=self.appointment_dates[0])

        is_available, appointment_date, num_available = check_available_date(self.target_weekday)
        self.assertTrue(is_available)
        self.assertGreater(num_available, 0)

    def test_check_for_appointment_no_available_dates(self):
        """Tests if check_for_appointment correctly handles fully booked schedules"""
        # Fully book all weeks for the requested weekday
        increment = 0
        for date in self.appointment_dates:
            for hour in range(9, 17):
                increment += 100
                AppointmentTable.objects.create(userID=hour, appointmentID=increment, start_time=time(hour, 0), end_time=time(hour + 1, 0), location="Office", date=date)

        response = self.client.post(self.url, {'SpeechResult': 'Tuesday'})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sorry, no available days on Tuesday for the next month.", str(response.content))
>>>>>>> 0770b6017857a4389007f908e95b57ceba07c74e
