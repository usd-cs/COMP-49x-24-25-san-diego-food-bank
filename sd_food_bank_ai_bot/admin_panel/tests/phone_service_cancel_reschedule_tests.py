from django.test import TestCase, Client
from ..models import User, AppointmentTable
from .phone_service_cancel_reschedule_tests import *
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

        self.assertIn("/INSERT_URL_TO_REROUTE_NO_APPOINTEMNT/", content)
    
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

        self.assertIn(f"/INSERT_URL_TO_CONFIRM_APPOINTMENT_CANCELLATION/{appointment.id}/", content)

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