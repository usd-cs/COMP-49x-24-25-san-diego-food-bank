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
        self.client = Client()
        self.appointment_date = now().date() + timedelta(days=(2 - now().weekday()) % 7)  # Next Tuesday
        self.url = reverse('check_for_appointment')  # Ensure this matches your URL patterns

        # Define business hours
        self.EARLIEST_TIME = time(9, 0)
        self.LATEST_TIME = time(17, 0)

        # Create sample appointments
        self.app1 = AppointmentTable.objects.create(
            userID=1, appointmentID=101, start_time=time(10, 0), end_time=time(11, 0),
            location="Office", date=self.appointment_date
        )
        self.app2 = AppointmentTable.objects.create(
            userID=2, appointmentID=102, start_time=time(12, 0), end_time=time(13, 0),
            location="Office", date=self.appointment_date
        )

    def test_check_for_appointment_valid_day(self):
        """Tests if check_for_appointment correctly identifies the next available appointment"""
        response = self.client.post(self.url, {'SpeechResult': 'Tuesday'})
        self.assertEqual(response.status_code, 200)
        self.assertIn("The soonest available appointment on Tuesday is at 09:00 AM", str(response.content))

    def test_check_for_appointment_invalid_day(self):
        """Tests if check_for_appointment correctly handles an invalid day"""
        response = self.client.post(self.url, {'SpeechResult': 'Blursday'})  # Invalid day
        self.assertEqual(response.status_code, 200)
        self.assertIn("I did not recognize that day", str(response.content))

    def test_find_next_available_time_with_gaps(self):
        """Tests find_next_available_time when gaps exist between appointments"""
        existing_appointments = AppointmentTable.objects.filter(date__date=self.appointment_date).order_by('start_time')
        available_time = find_next_available_time(existing_appointments)
        self.assertEqual(available_time, self.EARLIEST_TIME)  # Earliest available is 9:00 AM

    def test_find_next_available_time_no_gaps(self):
        """Tests find_next_available_time when appointments take the full schedule"""
        # Fill the entire schedule with appointments (9AM - 5PM back-to-back)
        AppointmentTable.objects.create(userID=3, appointmentID=103, start_time=time(9, 0), end_time=time(10, 0), date=self.appointment_date)
        AppointmentTable.objects.create(userID=4, appointmentID=104, start_time=time(11, 0), end_time=time(12, 0), date=self.appointment_date)
        AppointmentTable.objects.create(userID=5, appointmentID=105, start_time=time(13, 0), end_time=time(14, 0), date=self.appointment_date)
        AppointmentTable.objects.create(userID=6, appointmentID=106, start_time=time(14, 0), end_time=time(15, 0), date=self.appointment_date)
        AppointmentTable.objects.create(userID=7, appointmentID=107, start_time=time(15, 0), end_time=time(16, 0), date=self.appointment_date)
        AppointmentTable.objects.create(userID=8, appointmentID=108, start_time=time(16, 0), end_time=time(17, 0), date=self.appointment_date)

        existing_appointments = AppointmentTable.objects.filter(date__date=self.appointment_date).order_by('start_time')
        available_time = find_next_available_time(existing_appointments)
        self.assertIsNone(available_time)  # No available slots

    def test_find_next_available_time_end_of_day(self):
        """Tests find_next_available_time when there's an opening at the end of the day"""
        # The last appointment ends at 3:00 PM, so 3:00 PM should be available
        AppointmentTable.objects.create(userID=3, appointmentID=103, start_time=time(9, 0), end_time=time(10, 0), date=self.appointment_date)
        AppointmentTable.objects.create(userID=4, appointmentID=104, start_time=time(11, 0), end_time=time(12, 0), date=self.appointment_date)
        AppointmentTable.objects.create(userID=5, appointmentID=105, start_time=time(13, 0), end_time=time(14, 0), date=self.appointment_date)
        AppointmentTable.objects.create(userID=6, appointmentID=106, start_time=time(14, 0), end_time=time(15, 0), date=self.appointment_date)
        AppointmentTable.objects.create(userID=7, appointmentID=107, start_time=time(15, 0), end_time=time(16, 0), date=self.appointment_date)
        
        existing_appointments = AppointmentTable.objects.filter(date__date=self.appointment_date).order_by('start_time')
        available_time = find_next_available_time(existing_appointments)
        self.assertEqual(available_time, time(16, 0))  # 3:00 PM should be the next available slot