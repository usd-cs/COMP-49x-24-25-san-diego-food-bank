import datetime
from django.test import TestCase, Client
from django.utils import timezone
from unittest.mock import patch
from models import AppointmentTable, User


class CancelAppointmentIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()

        # Set up a test phone number for a Spanish speaking caller.
        self.test_phone = "+1234567890"
        self.user_es = User.objects.create(
            phone_number=self.test_phone,
            language="es",
            first_name="Test",
            last_name="User"
        )

        # Create an appointment associated with the Spanish user.
        self.appointment = AppointmentTable.objects.create(
            user=self.user_es,
            date=timezone.now().date() + datetime.timedelta(days=1),
            start_time=(timezone.now() + datetime.timedelta(hours=1)).time()
        )

    @patch("sd_food_bank_ai_bot/admin_panel/views.send_sms")  
    def test_cancel_appointment_success_spanish(self, mock_send_sms):
        """
        Tests that a cancellation request for an existing appointment returns
        a Spanish cancellation message and that the SMS is sent with the Spanish text.
        """
        url = f"/cancel_appointment/{self.appointment.id}/"
        response = self.client.post(url, data={"From": self.test_phone})

        # Verify that send_sms was called with a message containing Spanish text
        self.assertTrue(mock_send_sms.called, "Expected send_sms to be called.")
        args, kwargs = mock_send_sms.call_args
        self.assertIn("Su cita", args[1], "Expected Spanish text in the SMS message.")

        # Check that the response contains part of the Spanish cancellation message
        self.assertIn("Su cita", response.content.decode(), "Expected Spanish cancellation message in the response.")

        # Verify the appointment has been deleted.
        with self.assertRaises(AppointmentTable.DoesNotExist):
            AppointmentTable.objects.get(pk=self.appointment.id)

    @patch("sd_food_bank_ai_bot/admin_panel/views.send_sms")  
    def test_cancel_appointment_not_found_spanish(self, mock_send_sms):
        """
        Tests that when an appointment is not found, the Spanish error message is returned,
        and no SMS is sent.
        """
        invalid_id = 99999  # An appointment id that does not exist.
        url = f"/cancel_appointment/{invalid_id}/"
        response = self.client.post(url, data={"From": self.test_phone})
        
        # Ensure send_sms was not called because no appointment was found.
        mock_send_sms.assert_not_called()

        # Check that the error message is in Spanish.
        self.assertIn(
            "No pudimos encontrar una cita para cancelar.", 
            response.content.decode(),
            "Expected Spanish error message in the response."
        )
