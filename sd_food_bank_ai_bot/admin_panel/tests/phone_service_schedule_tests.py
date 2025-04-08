from django.test import TestCase, RequestFactory, Client
from admin_panel.views.phone_service_schedule import (get_phone_number, get_name,
                                                      process_name_confirmation, check_available_date,
                                                      confirm_account, get_available_times_for_date)
from unittest.mock import patch, MagicMock
import xml.etree.ElementTree as ET
from django.urls import reverse
from django.utils.timezone import now
from datetime import timedelta, time, datetime, date
from ..models import User, AppointmentTable, Log
import urllib.parse
from django.utils import timezone


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

    def parse_twiml(self, content):
        """Helper method to parse TwiML response and return the root element"""
        return ET.fromstring(content)

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_no_account_reroute_yes(self, mock_get_response_sentiment):
        """
        If the user says 'yes', they should be rerouted to the main menu (/answer/)
        """
        mock_get_response_sentiment.return_value = True
        response = self.client.post(
            reverse("no_account_reroute"),
            {"SpeechResult": "yes"}
        )
        self.assertEqual(response.status_code, 200)
        # Parse the TwiML response
        root = self.parse_twiml(response.content.decode("utf-8"))

        say_elems = root.findall(".//Say")
        self.assertTrue(any("Returning you to the main menu" in (elem.text or "") for elem in say_elems))

        # Check for <Redirect> to /answer/
        redirect_elem = root.find("Redirect")
        self.assertIsNotNone(redirect_elem, "Expected a <Redirect> element when user says yes.")
        self.assertEqual(redirect_elem.text, "/answer/")

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_no_account_reroute_no(self, mock_get_response_sentiment):
        """
        If user says 'no', the call should be hung up.
        """
        mock_get_response_sentiment.return_value = False
        response = self.client.post(
            reverse("no_account_reroute"),
            {"SpeechResult": "no"}
        )
        self.assertEqual(response.status_code, 200)

        root = self.parse_twiml(response.content.decode("utf-8"))
        say_elems = root.findall(".//Say")
        self.assertTrue(any("Goodbye" in (elem.text or "") for elem in say_elems))

        # Check for a <Hangup> element
        hangup_elem = root.find("Hangup")
        self.assertIsNotNone(hangup_elem, "Expected a <Hangup> element when user says no.")


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
        self.assertIn("request_date_availability", response.content.decode())

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_process_name_confirmation_valid_with_middle(self, mock_get_response_sentiment):
        """Test all valid data with first, middle, and last name"""
        mock_get_response_sentiment.return_value = True

        name = "Billy Joseph Bob"
        name_encoded = urllib.parse.quote(name)
        request = self.factory.post(f"/process_name_confirmation/{name_encoded}/", {"From": "+16294968156"})
        response = process_name_confirmation(request, name_encoded)

        self.assertTrue(User.objects.filter(phone_number="+16294968156", first_name="Billy", last_name="Bob").exists())
        self.assertIn("request_date_availability", response.content.decode())

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_process_name_confirmation_valid_with_no_last(self, mock_get_response_sentiment):
        """Test all valid data with no last name"""
        mock_get_response_sentiment.return_value = True

        name = "Billy"
        name_encoded = urllib.parse.quote(name)
        request = self.factory.post(f"/process_name_confirmation/{name_encoded}/", {"From": "+16294968155"})
        response = process_name_confirmation(request, name_encoded)

        self.assertTrue(User.objects.filter(phone_number="+16294968155", first_name="Billy").exists())
        self.assertIn("request_date_availability", response.content.decode())

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
        self.target_weekday = 1  # Gets Tuesday
        self.url = reverse('check_for_appointment')  # Ensure this matches your URL patterns

        # Define business hours
        self.EARLIEST_TIME = time(9, 0)
        self.LATEST_TIME = time(17, 0)

        # Create a test user
        self.test_user = User.objects.create(first_name="John", last_name="Doe", phone_number="+1234567890")

        # Generate appointment dates for the next 4 weeks on Tuesday
        self.appointment_dates = [
            self.today + timedelta(days=(self.target_weekday - self.today.weekday()) % 7 + (week * 7)) for week in range(4)
        ]

        self.appointment_dates = [
            timezone.make_aware(datetime.combine(
                self.today + timedelta(days=(self.target_weekday - self.today.weekday()) % 7 + (week * 7)),
                time(0, 0))) for week in range(4)
                ]

    @patch("admin_panel.views.utilities.OpenAI")
    def test_check_for_appointment_valid_day(self, mock_openai):
        """Tests if check_for_appointment correctly identifies available days"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Tuesday"))]
        )
        response = self.client.post(self.url, {'SpeechResult': 'Tuesday'})
        self.assertEqual(response.status_code, 200)
        self.assertIn("The next available Tuesday", str(response.content))

    def test_check_available_date_with_no_appointments(self):
        """Tests check_available_date when no appointments exist (should be fully open)"""
        is_available, appointment_date, num_available = check_available_date(self.target_weekday)
        self.assertTrue(is_available)
        self.assertEqual(num_available, 4)  # Default 4 slots

    def test_check_available_date_with_full_schedule(self):
        """Tests check_available_date when all slots are taken"""
        for avail_date in self.appointment_dates:
            for hour in range(9, 17):
                AppointmentTable.objects.create(
                    user=self.test_user,
                    start_time=time(hour, 0),
                    end_time=time(hour + 1, 0),
                    location="Office",
                    date=avail_date
                )

        is_available, appointment_date, num_available = check_available_date(self.target_weekday)
        self.assertFalse(is_available)
        self.assertIsNone(appointment_date)
        self.assertEqual(num_available, 0)

    def test_check_available_date_with_partial_availability(self):
        """Tests check_available_date when there are some open slots"""
        AppointmentTable.objects.create(
            user=self.test_user,
            start_time=self.EARLIEST_TIME,
            end_time=time(10, 0),
            location="Office",
            date=self.appointment_dates[0]
        )

        is_available, appointment_date, num_available = check_available_date(self.target_weekday)
        self.assertTrue(is_available)
        self.assertGreater(num_available, 0)

    @patch("admin_panel.views.utilities.OpenAI")
    def test_check_for_appointment_no_available_dates(self, mock_openai):
        """Tests if check_for_appointment correctly handles fully booked schedules"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Tuesday"))]
        )

        # Fully book all weeks for the requested weekday
        for avail_date in self.appointment_dates:
            for hour in range(9, 17):
                AppointmentTable.objects.create(
                    user=self.test_user,
                    start_time=time(hour, 0),
                    end_time=time(hour + 1, 0),
                    location="Office",
                    date=avail_date
                )

        response = self.client.post(self.url, {'SpeechResult': 'Tuesday'})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sorry, no available days on Tuesday for the next month.", str(response.content))


class AppointmentSchedulingTests(TestCase):
    def setUp(self):
        """Setup test data for scheduling appointments"""
        self.client = Client()
        self.factory = RequestFactory()
        self.today = now().date()
        self.target_weekday = 1  # Tuesday
        self.EARLIEST_TIME = time(9, 0)
        self.LATEST_TIME = time(17, 0)

        # Create a test user
        self.test_user = User.objects.create(first_name="John", last_name="Doe", phone_number="+1234567890")

        # Sample appointment times
        self.appointment_times = [time(10, 0), time(14, 30), time(16, 45)]

        # Generate appointment dates for next 4 weeks on Tuesday
        self.appointment_dates = [
            self.today + timedelta(days=(self.target_weekday - self.today.weekday()) % 7 + (week * 7))
            for week in range(4)
        ]

#         self.appointment_dates = [
#     make_aware(datetime.combine(
#         self.today + timedelta(days=(self.target_weekday - self.today.weekday()) % 7 + (week * 7)),
#         time(0, 0)
#     )) for week in range(4)
# ]

        # Create sample appointments in the database
        for avail_date in self.appointment_dates:
            for appt_time in self.appointment_times:
                AppointmentTable.objects.create(
                    user=self.test_user,
                    start_time=appt_time,
                    end_time=(datetime.combine(avail_date, appt_time) + timedelta(minutes=30)).time(),
                    location="Office",
                    date=avail_date
                )

    def test_request_preferred_time_under_four(self):
        """Tests if available times are correctly listed when ≤ 3 slots exist."""
        url = reverse('request_preferred_time_under_four') + f"?date={self.appointment_dates[0]}"
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Here are the available times", response.content.decode())

    def test_request_preferred_time_over_three(self):
        """Tests if prompt correctly asks for a preferred time when >3 slots exist."""
        url = reverse('request_preferred_time_over_three') + f"?date={self.appointment_dates[0]}"
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("What time would you like?", response.content.decode())

    @patch("admin_panel.views.phone_service_schedule.OpenAI")
    def test_generate_requested_time(self, mock_openai):
        """Tests if the system correctly extracts time using GPT."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="2:45 PM"))]
        )

        url = reverse('generate_requested_time') + f"?date={self.appointment_dates[0]}"
        response = self.client.post(url, {"SpeechResult": "Can I come at 2:45 PM?"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Your requested time was 2:45 PM", response.content.decode())

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment", return_value=True)
    def test_find_requested_time_exact_match(self, mock_get_response_sentiment):
        """Tests if find_requested_time correctly finds an exact time match."""
        time_encoded = urllib.parse.quote("02:30 PM")
        url = reverse('find_requested_time', args=[time_encoded]) + f"?date={self.appointment_dates[0]}"
        response = self.client.post(url, {"SpeechResult": "yes"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Our nearest appointment slot is", response.content.decode())

    def test_get_available_times_for_date(self):
        """Tests if available times are correctly retrieved."""
        available_times = get_available_times_for_date(self.appointment_dates[0])
        self.assertEqual(len(available_times), 3)
        self.assertIn(time(9, 0), available_times)
        self.assertIn(time(10, 30), available_times)
        self.assertIn(time(15, 0), available_times)


class AppointmentConfirmationTests(TestCase):

    def setUp(self):
        """Set up resources for tests"""
        self.client = Client()

        User.objects.create(
                first_name="Billy",
                last_name="Bob",
                phone_number="+16191234567",
                email=None
        )

        User.objects.create(
                first_name="Yilly",
                last_name="Yob",
                phone_number="+16197654321",
                email=None
        )

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_given_time_response_affirmative(self, mock_get_response_sentiment):
        """Tests an affirmative response to the given time"""
        mock_get_response_sentiment.return_value = True

        time_request = "11:30 AM"
        time_request_encoded = urllib.parse.quote(time_request)
        date_encoded = "2025-03-04"
        content = {"SpeechResult": "That is correct."}
        response = self.client.post(f"/given_time_response/{time_request_encoded}/{date_encoded}/", content)
        content = response.content.decode("utf-8")

        self.assertNotIn(f"<Redirect>/request_preferred_time_under_four/?date={date_encoded}</Redirect>", content)
        self.assertIn(f"<Redirect>/confirm_time_selection/{time_request_encoded}/{date_encoded}/</Redirect>", content)

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_given_time_response_negative(self, mock_get_response_sentiment):
        """Tests a negative response to the given time"""
        mock_get_response_sentiment.return_value = False

        time_request = "11:30 AM"
        time_request_encoded = urllib.parse.quote(time_request)
        date_encoded = "2025-03-04"

        content = {"SpeechResult": "That is incorrect."}
        response = self.client.post(f"/given_time_response/{time_request_encoded}/{date_encoded}/", content)
        content = response.content.decode("utf-8")

        self.assertNotIn(f"<Redirect>/confirm_time_selection/{time_request_encoded}/{date_encoded}/</Redirect>", content)
        self.assertIn(f"<Redirect>/request_preferred_time_under_four/?date={date_encoded}</Redirect>", content)

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_suggested_time_response_affirmative(self, mock_get_response_sentiment):
        """Tests an affirmative response to the suggested time"""
        mock_get_response_sentiment.return_value = True

        time_request = "11:30 AM"
        time_request_encoded = urllib.parse.quote(time_request)
        date_encoded = "2025-03-04"

        content = {"SpeechResult": "That is correct."}
        response = self.client.post(f"/suggested_time_response/{time_request_encoded}/{date_encoded}/", content)
        content = response.content.decode("utf-8")

        self.assertNotIn(f"<Redirect>/request_preferred_time_over_three/?date={date_encoded}</Redirect>", content)
        self.assertIn(f"<Redirect>/confirm_time_selection/{time_request_encoded}/{date_encoded}/</Redirect>", content)

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_suggested_time_response_negative(self, mock_get_response_sentiment):
        """Tests a negative response to the suggested time"""
        mock_get_response_sentiment.return_value = False

        time_request = "11:30 AM"
        time_request_encoded = urllib.parse.quote(time_request)
        date_encoded = "2025-03-04"

        content = {"SpeechResult": "No."}
        response = self.client.post(f"/suggested_time_response/{time_request_encoded}/{date_encoded}/", content)
        content = response.content.decode("utf-8")

        self.assertNotIn(f"<Redirect>/confirm_time_selection/{time_request_encoded}/{date_encoded}/</Redirect>", content)
        self.assertIn(f"<Redirect>/request_preferred_time_over_three/?date={date_encoded}</Redirect>", content)

    def test_confirm_time_selection_th(self):
        """Tests proper message is sent for give user, date, and time"""
        time_request = "11:30 AM"
        time_request_encoded = urllib.parse.quote(time_request)

        date_encoded = "2025-03-04"
        expected_date_str = "Tuesday, March 04th"

        content = {"From": "+16191234567"}
        response = self.client.post(f"/confirm_time_selection/{time_request_encoded}/{date_encoded}/", content)
        content = response.content.decode("utf-8")

        self.assertIn(f"Great! To confirm you are booked for {expected_date_str} at {time_request} and your name is Billy Bob. Is that correct?", content)
        self.assertIn(f'action="/final_confirmation/{time_request_encoded}/{date_encoded}/"', content)

    def test_confirm_time_selection_st(self):
        """Tests proper message is sent for give user, date, and time"""
        time_request = "11:30 AM"
        time_request_encoded = urllib.parse.quote(time_request)

        date_encoded = "2025-03-01"
        expected_date_str = "Saturday, March 01st"

        content = {"From": "+16191234567"}
        response = self.client.post(f"/confirm_time_selection/{time_request_encoded}/{date_encoded}/", content)
        content = response.content.decode("utf-8")

        self.assertIn(f"Great! To confirm you are booked for {expected_date_str} at {time_request} and your name is Billy Bob. Is that correct?", content)
        self.assertIn(f'action="/final_confirmation/{time_request_encoded}/{date_encoded}/"', content)

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_final_confirmation_affirmative(self, mock_get_response_sentiment):
        """Test giving an affirmative response to the final confirmation"""
        mock_get_response_sentiment.return_value = True
        time_request = "11:30 AM"
        time_request_encoded = urllib.parse.quote(time_request)
        date_encoded = "2025-03-01"

        content = {"From": "+16191234567"}
        response = self.client.post(f"/final_confirmation/{time_request_encoded}/{date_encoded}/", content)
        content = response.content.decode("utf-8")

        user = User.objects.get(phone_number="+16191234567")
        date_obj = datetime.strptime(date_encoded, '%Y-%m-%d').date()
        start = datetime.strptime(time_request, '%I:%M %p').time()
        end = datetime.strptime("11:45 AM", '%I:%M %p').time()

        self.assertTrue(AppointmentTable.objects.filter(user=user, start_time=start, end_time=end, date=date_obj).exists())
        self.assertIn("Perfect! Your appointment has been scheduled. You'll receive a confirmation SMS shortly. Have a great day!", content)

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_final_confirmation_negative(self, mock_get_response_sentiment):
        """Test giving an negative response to the final confirmation"""
        mock_get_response_sentiment.return_value = False

        time_request = "11:30 AM"
        time_request_encoded = urllib.parse.quote(time_request)
        date_encoded = "2025-03-01"

        content = {"From": "+16191234567"}
        response = self.client.post(f"/final_confirmation/{time_request_encoded}/{date_encoded}/", content)
        content = response.content.decode("utf-8")

        user = User.objects.get(phone_number="+16191234567")
        date_obj = datetime.strptime(date_encoded, '%Y-%m-%d').date()
        start = datetime.strptime(time_request, '%I:%M %p').time()
        end = datetime.strptime("12:00 PM", '%I:%M %p').time()

        self.assertFalse(AppointmentTable.objects.filter(user=user, start_time=start, end_time=end, date=date_obj).exists())
        self.assertNotIn(
            "Perfect! Your appointment has been scheduled. You'll receive a confirmation SMS shortly. Have a great day!",
            content)
        self.assertIn("<Redirect>/answer/</Redirect>", content)


class CancelAppointmentFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            first_name="Billy",
            last_name="Bob",
            phone_number="+1234567890"
        )
        self.appointment = AppointmentTable.objects.create(
            user=self.user,
            date=timezone.make_aware(datetime.combine((now() + timedelta(days=1)).date(), time(0, 0))),
            start_time=time(9, 0),
            end_time=time(9, 30),
            location="Foodbank"
        )

    def parse_twiML(self, twiml_str):
        """
        Helper to parse the TwiML XMl
        """
        return ET.fromstring(twiml_str)

    def test_cancel_appointment_valid(self):
        """
        Test that a valid appointment_id is deleted and the caller is informed that
        the appointment has been canceled.
        """
        url = reverse("cancel_appointment", args=[self.appointment.pk])
        response = self.client.post(url, {"From": self.user.phone_number})
        self.assertEqual(response.status_code, 200)

        self.assertFalse(AppointmentTable.objects.filter(pk=self.appointment.pk).exists())

        content = response.content.decode("utf-8")
        root = self.parse_twiML(content)

        say_text = " ".join(elem.text for elem in root.findall(".//Say") if elem.text)
        self.assertIn("Your appointment has been canceled", say_text)


class RescheduleAppointmentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            first_name="Brendan",
            last_name="Bost",
            phone_number="+1234567890"
        )
        # tomorrow = now().date() + timedelta(days=1)
        tomorrow = timezone.make_aware(datetime.combine(now().date() + timedelta(days=1), time(0, 0)))
        start_time = time(10, 0)

        # end_time = (datetime.combine(date.today(), start_time) + timedelta(minutes=30)).time()
        end_time = (datetime.combine(timezone.localdate(), start_time) + timedelta(minutes=30)).time()
        self.appointment = AppointmentTable.objects.create(
            user=self.user,
            date=tomorrow,
            start_time=start_time,
            end_time=end_time,
            location="Foodbank"
        )

    def parse_twiML(self, twiml_str):
        """Parse TwiML XML"""
        return ET.fromstring(twiml_str)

    def test_reschedule_with_existing_appointment(self):
        """
        When caller has an appointment, reschedule_appointment should cancel it and
        redirect to the scheduling flow.
        """
        date_encoded = urllib.parse.quote("2025-05-01")
        url = reverse("reschedule_appointment", args=[date_encoded])

        response = self.client.post(url, {"From": self.user.phone_number})
        self.assertFalse(AppointmentTable.objects.filter(pk=self.appointment.pk).exists())

        twiml = response.content.decode("utf-8")
        root = self.parse_twiML(twiml)

        say_text = " ".join(elem.text for elem in root.findall(".//Say") if elem.text)
        self.assertIn("Your appointment has been canceled.", say_text)
        self.assertIn("Let's schedule a new appointment.", say_text)
        # Make sure there's a redirect to the scheduling flow.
        redirect_elem = root.find("Redirect")
        self.assertIsNotNone(redirect_elem)
        self.assertEqual(redirect_elem.text, "/request_date_availability/")

    def test_reschedule_without_existing_appointment(self):
        """
        When the caller doesn't have an appointment, the response should indicate
        that no appointment is scheduled and then route to scheduling a new appointment.
        """
        # Delete the appointment to simulate there isn't a scheduled appointment.
        self.appointment.delete()
        date_encoded = urllib.parse.quote("2025-05-01")
        url = reverse("reschedule_appointment", args=[date_encoded])

        response = self.client.post(url, {"From": self.user.phone_number})

        self.assertEqual(response.status_code, 200)

        twiml = response.content.decode("utf-8")
        root = self.parse_twiML(twiml)
        say_text = " ".join(elem.text for elem in root.findall(".//Say") if elem.text)

        self.assertIn("You do not have an appointment scheduled.", say_text)
        self.assertIn("Let's schedule a new appointment.", say_text)
        redirect_elem = root.find("Redirect")
        self.assertIsNotNone(redirect_elem)
        self.assertEqual(redirect_elem.text, "/request_date_availability/")


class ConfirmAccountRescheduleTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.phone_number = "+1234567890"
        self.user = User.objects.create(phone_number=self.phone_number, first_name="John", last_name="Doe")
        self.log = Log.objects.create(phone_number=self.phone_number)

    def _mock_request(self):
        return self.factory.post("/confirm_account/?action=reschedule", {"SpeechResult": "yes"})

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment", return_value=True)
    @patch("admin_panel.views.phone_service_schedule.get_phone_number", return_value="+1234567890")
    @patch("admin_panel.views.phone_service_schedule.appointment_count", return_value=0)
    def test_reschedule_zero_appointments(self, mock_count, mock_phone, mock_sentiment):
        request = self._mock_request()
        response = confirm_account(request)
        self.assertIn("We do not have an appointment registered", response.content.decode())

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment", return_value=True)
    @patch("admin_panel.views.phone_service_schedule.get_phone_number", return_value="+1234567890")
    @patch("admin_panel.views.phone_service_schedule.appointment_count", return_value=1)
    def test_reschedule_one_appointment(self, mock_count, mock_phone, mock_sentiment):
        request = self._mock_request()
        response = confirm_account(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("/reschedule_appointment/None/", response.content.decode())

    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment", return_value=True)
    @patch("admin_panel.views.phone_service_schedule.get_phone_number", return_value="+1234567890")
    @patch("admin_panel.views.phone_service_schedule.appointment_count", return_value=2)
    def test_reschedule_multiple_appointments(self, mock_count, mock_phone, mock_sentiment):
        request = self._mock_request()
        response = confirm_account(request)
        self.assertIn("/prompt_reschedule_appointment_over_one/", response.content.decode())
