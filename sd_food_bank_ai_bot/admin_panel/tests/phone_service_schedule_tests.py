from django.test import TestCase, RequestFactory, Client
from admin_panel.views.phone_service_schedule import *
from unittest.mock import patch, MagicMock
import xml.etree.ElementTree as ET
from django.urls import reverse
from django.utils.timezone import now
from datetime import timedelta, time
from ..models import User, AppointmentTable


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
