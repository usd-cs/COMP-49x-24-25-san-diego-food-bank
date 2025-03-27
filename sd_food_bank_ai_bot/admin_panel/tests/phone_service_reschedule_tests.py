from django.test import TestCase, RequestFactory
from unittest.mock import patch
from admin_panel.models import User, AppointmentTable
from admin_panel.views.phone_service_reschedule import (
    check_account_cancel_reschedule,
    confirm_account_cancel_reschedule,
)
from datetime import datetime, time as dt_time

class Confirm_Account_CancelRescheduleTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.phone_number = "+1234567890"
        self.user = User.objects.create(
            first_name="John", last_name="Doe", phone_number=self.phone_number
        )

    @patch("admin_panel.views.phone_service_reschedule.get_phone_number")
    def test_check_account_cancel_reschedule_success(self, mock_get_phone_number):
        mock_get_phone_number.return_value = self.phone_number
        request = self.factory.post("/check_account_cancel_reschedule/")
        response = check_account_cancel_reschedule(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Hello, John Doe", response.content)

    @patch("admin_panel.views.phone_service_reschedule.get_response_sentiment", return_value=True)
    @patch("admin_panel.views.phone_service_reschedule.get_phone_number")
    def test_confirm_account_cancel_reschedule_with_appointments(self, mock_get_phone_number, mock_sentiment):
        AppointmentTable.objects.create(
            user=self.user,
            start_time=dt_time(10, 0),
            end_time=dt_time(10, 30),
            date=datetime.now().date()
        )
        mock_get_phone_number.return_value = self.phone_number
        request = self.factory.post("/confirm_account_cancel_reschedule/", data={"SpeechResult": "yes"})
        response = confirm_account_cancel_reschedule(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your account has been confirmed", response.content)

    @patch("admin_panel.views.phone_service_reschedule.get_response_sentiment", return_value=True)
    @patch("admin_panel.views.phone_service_reschedule.get_phone_number")
    def test_confirm_account_cancel_reschedule_no_appointments(self, mock_get_phone_number, mock_sentiment):
        mock_get_phone_number.return_value = self.phone_number
        request = self.factory.post("/confirm_account_cancel_reschedule/", data={"SpeechResult": "yes"})
        response = confirm_account_cancel_reschedule(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You do not have any appointments scheduled", response.content)

    @patch("admin_panel.views.phone_service_reschedule.get_response_sentiment", return_value=False)
    @patch("admin_panel.views.phone_service_reschedule.get_phone_number")
    def test_confirm_account_cancel_reschedule_negative(self, mock_get_phone_number, mock_sentiment):
        mock_get_phone_number.return_value = self.phone_number
        request = self.factory.post("/confirm_account_cancel_reschedule/", data={"SpeechResult": "no"})
        response = confirm_account_cancel_reschedule(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"I'm sorry, please try again", response.content)
