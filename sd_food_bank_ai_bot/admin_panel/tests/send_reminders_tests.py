from django.core.management import call_command
from django.test import TestCase
from unittest.mock import patch
from datetime import timedelta
from django.utils.timezone import now
from admin_panel.models import User, AppointmentTable


class SendRemindersCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            first_name="Test",
            last_name="User",
            phone_number="+1234567890"
        )

    @patch("admin_panel.management.commands.send_reminders.send_sms")
    def test_send_reminder_sms_sent(self, mock_send_sms):
        """Tests that an SMS is sent for a valid appointment 24h in advance"""
        appt_time = now() + timedelta(hours=24, minutes=2)
        AppointmentTable.objects.create(
            user=self.user,
            date=appt_time.date(),
            start_time=appt_time.time(),
            end_time=(appt_time + timedelta(minutes=15)).time()
        )

        call_command("send_reminders")
        mock_send_sms.assert_called_once()
        self.assertIn("Reminder", mock_send_sms.call_args[0][1])

    @patch("admin_panel.management.commands.send_reminders.send_sms")
    def test_no_sms_sent_outside_reminder_window(self, mock_send_sms):
        """Tests that no SMS is sent if the appointment is outside the 24h window"""
        # Appointment is too early (23 hours)
        early_time = now() + timedelta(hours=23)
        AppointmentTable.objects.create(
            user=self.user,
            date=early_time.date(),
            start_time=early_time.time(),
            end_time=(early_time + timedelta(minutes=15)).time()
        )

        # Appointment is too late (25 hours)
        late_time = now() + timedelta(hours=25)
        AppointmentTable.objects.create(
            user=self.user,
            date=late_time.date(),
            start_time=late_time.time(),
            end_time=(late_time + timedelta(minutes=15)).time()
        )

        call_command("send_reminders")
        mock_send_sms.assert_not_called()

    @patch("admin_panel.management.commands.send_reminders.send_sms")
    def test_sms_failure_handled_gracefully(self, mock_send_sms):
        """Tests that an exception during SMS sending does not crash the command"""
        appt_time = now() + timedelta(hours=24, minutes=2)
        AppointmentTable.objects.create(
            user=self.user,
            date=appt_time.date(),
            start_time=appt_time.time(),
            end_time=(appt_time + timedelta(minutes=15)).time()
        )

        mock_send_sms.side_effect = Exception("Twilio is down")
        call_command("send_reminders")
        # It should not raise or crash even with exception
        self.assertTrue(True)

    @patch("admin_panel.management.commands.send_reminders.send_sms")
    def test_multiple_appointments_within_window(self, mock_send_sms):
        """Tests that multiple reminders are sent for multiple appointments in window"""
        for minute in range(1, 4):  # Create 3 appointments within window
            appt_time = now() + timedelta(hours=24, minutes=minute)
            AppointmentTable.objects.create(
                user=self.user,
                date=appt_time.date(),
                start_time=appt_time.time(),
                end_time=(appt_time + timedelta(minutes=15)).time()
            )

        call_command("send_reminders")
        self.assertEqual(mock_send_sms.call_count, 3)
