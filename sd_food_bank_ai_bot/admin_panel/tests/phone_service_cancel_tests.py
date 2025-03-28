from django.test import TestCase, Client
from ..models import User, AppointmentTable
from .phone_service_cancel_tests import *
from unittest.mock import patch
from datetime import datetime
import urllib.parse

class CancelInitialRoutingTests(TestCase):
    def setUp(self):
        """Set up client and database for use during testing"""
        self.client = Client()
        self.test_user_phone_number = "+1234567890"

        self.test_user = User.objects.create(
            first_name="Billy",
            last_name="Bob",
            phone_number=self.test_user_phone_number,
            email="billybob@email.com"
        )
    
    def test_cancel_initial_routing_no_appointment(self):
        """Test routed correctly when the user has no appointment"""
        content = {"From": self.test_user_phone_number}
        response = self.client.post("/cancel_initial_routing/", content)
        content = response.content.decode("utf-8")

        self.assertIn("/reroute_no_appointment/", content)
    
    def test_cancel_initial_routing_one_appointment(self):
        """Test routed correctly when the user has one appointment"""
        appointment = AppointmentTable.objects.create(
            user=self.test_user,
            start_time=datetime.strptime("2:30 PM", '%I:%M %p').time(),
            end_time=datetime.strptime("3:00 PM", '%I:%M %p').time(),
            date=datetime.strptime("2025-03-26", '%Y-%m-%d').date()
        )

        content = {"From": self.test_user_phone_number}
        response = self.client.post("/cancel_initial_routing/", content)
        content = response.content.decode("utf-8")

        self.assertIn(f"/prompt_cancellation_confirmation/{appointment.id}/", content)

    def test_cancel_initial_routing_many_appointments(self):
        """Test routed correctly when the user has many appointments"""
        AppointmentTable.objects.create(
            user=self.test_user,
            start_time=datetime.strptime("2:30 PM", '%I:%M %p').time(),
            end_time=datetime.strptime("3:00 PM", '%I:%M %p').time(),
            date=datetime.strptime("2025-03-26", '%Y-%m-%d').date()
        )

        AppointmentTable.objects.create(
            user=self.test_user,
            start_time=datetime.strptime("12:30 PM", '%I:%M %p').time(),
            end_time=datetime.strptime("1:00 PM", '%I:%M %p').time(),
            date=datetime.strptime("2025-03-28", '%Y-%m-%d').date()
        )

        content = {"From": self.test_user_phone_number}
        response = self.client.post("/cancel_initial_routing/", content)
        content = response.content.decode("utf-8")

        self.assertIn("/INSERT_URL_TO_ASKING_FOR_APPOINTMENT/", content)
    
    def test_reroute_no_appointment(self):
        """
        Test that the user is properly prompted and redirected.
        """
        content = {"From": self.test_user_phone_number}
        response = self.client.post("/reroute_no_appointment/", content)
        content = response.content.decode("utf-8")

        self.assertIn("We do not have an appointment registered with your number.", content)
        self.assertIn("Would you like to go back to the main menu?", content)
        self.assertIn("/return_main_menu_repsonse/", content)
    
    @patch("admin_panel.views.phone_service_schedule.get_response_sentiment")
    def test_confirm_account_with_cancel(self, mock_get_response_sentiment):
        """
        Test that the call is properly routed in confirm account with the cancel option
        """
        mock_get_response_sentiment.return_value = True
        
        content = {"SpeechResult": "Yes, that is correct."}
        response = self.client.post("/confirm_account/?action=cancel", content)
        content = response.content.decode("utf-8")

        self.assertIn("/cancel_initial_routing/", content)


class CancelConfirmationTests(TestCase):
    def setUp(self):
        """
        Set up database and client for use during tests
        """
        self.client = Client()
        self.test_user_phone_number = "+1234567890"

        self.test_user = User.objects.create(
            first_name="Billy",
            last_name="Bob",
            phone_number=self.test_user_phone_number,
            email="billybob@email.com"
        )
    
        self.appointment = AppointmentTable.objects.create(
            user=self.test_user,
            start_time=datetime.strptime("2:30 PM", '%I:%M %p').time(),
            end_time=datetime.strptime("3:00 PM", '%I:%M %p').time(),
            date=datetime.strptime("2025-03-26", '%Y-%m-%d').date()
        )

        AppointmentTable.objects.create(
            user=self.test_user,
            start_time=datetime.strptime("12:30 PM", '%I:%M %p').time(),
            end_time=datetime.strptime("1:00 PM", '%I:%M %p').time(),
            date=datetime.strptime("2025-03-28", '%Y-%m-%d').date()
        )
    
    def test_prompt_cancel_confirmation(self):
        """
        Test that the user is prompted with the proper information to cancel their appointment.
        """
        content = {"From": self.test_user_phone_number}
        response = self.client.post(f"/prompt_cancellation_confirmation/{self.appointment.id}/", content)
        content = response.content.decode("utf-8")

        self.assertIn(f"Are you sure you want to cancel your appointment on Wednesday, March 26th at 02:30 PM?", content)
        self.assertIn("/cancellation_confirmation/", content)
    
    @patch("admin_panel.views.phone_service_cancel.get_response_sentiment")
    def test_cancellation_confirmation_affirmative(self, mock_get_response_sentiment):
        """
        Test when the user gives an affirmative response to cancelling the appointment.
        """
        mock_get_response_sentiment.return_value = True

        content = {"SpeechResult": "Yes, that is correct."}
        response = self.client.post(f"/cancellation_confirmation/{self.appointment.id}/", content)
        content = response.content.decode("utf-8")

        self.assertIn(f"/cancel_appointment/{self.appointment.id}/", content)
    
    @patch("admin_panel.views.phone_service_cancel.get_response_sentiment")
    def test_cancellation_confirmation_negative(self, mock_get_response_sentiment):
        """
        Test when the user gives a negative response to cancelling the appointment.
        """
        mock_get_response_sentiment.return_value = False

        content = {"SpeechResult": "No."}
        response = self.client.post(f"/cancellation_confirmation/{self.appointment.id}/", content)
        content = response.content.decode("utf-8")

        self.assertIn("Would you like to go back to the main menu?", content)
        self.assertIn("/return_main_menu_repsonse/", content)
    
    @patch("admin_panel.views.phone_service_cancel.get_response_sentiment")
    def test_cancellation_confirmation_no_response(self, mock_get_response_sentiment):
        """
        Test when the user gives no response to cancelling the appointment.
        """
        mock_get_response_sentiment.return_value = False

        content = {"SpeechResult": ""}
        response = self.client.post(f"/cancellation_confirmation/{self.appointment.id}/", content)
        content = response.content.decode("utf-8")

        mock_get_response_sentiment.assert_not_called()
        self.assertIn(f"/prompt_cancellation_confirmation/{self.appointment.id}/", content)
    
    @patch("admin_panel.views.phone_service_cancel.get_response_sentiment")
    def test_return_main_menu_response_affirmative(self, mock_get_response_sentiment):
        """
        Test when the user gives an affirmative response to going to main menu.
        """
        mock_get_response_sentiment.return_value = True

        content = {"SpeechResult": "Yes please."}
        response = self.client.post("/return_main_menu_response/", content)
        content = response.content.decode("utf-8")

        self.assertIn("/answer/", content)
    
    @patch("admin_panel.views.phone_service_cancel.get_response_sentiment")
    def test_return_main_menu_response_negative(self, mock_get_response_sentiment):
        """
        Test when the user gives a negative response to going to main menu.
        """
        mock_get_response_sentiment.return_value = False

        content = {"SpeechResult": "No thank you."}
        response = self.client.post("/return_main_menu_response/", content)
        content = response.content.decode("utf-8")

        self.assertIn("Have a great day!", content)
        self.assertIn("<Hangup />", content)
    
    @patch("admin_panel.views.phone_service_cancel.get_response_sentiment")
    def test_return_main_menu_response_no_response(self, mock_get_response_sentiment):
        """
        Test when the user gives no response to going to main menu.
        """
        mock_get_response_sentiment.return_value = False

        content = {"SpeechResult": ""}
        response = self.client.post("/return_main_menu_response/", content)
        content = response.content.decode("utf-8")

        mock_get_response_sentiment.assert_not_called()
        self.assertIn("Would you like to go back to the main menu?", content)
        self.assertIn("/return_main_menu_repsonse/", content)