from django.test import TestCase, RequestFactory
from unittest.mock import patch, MagicMock, call
from admin_panel.models import User, AppointmentTable
from admin_panel.views.phone_service_reschedule import (
    prompt_reschedule_appointment_over_one,
    generate_requested_date,
    confirm_requested_date
)
from datetime import datetime, timedelta, time
import urllib.parse
import xml.etree.ElementTree as ET
from django.utils import timezone


class PhoneServiceRescheduleTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create(
            first_name="Test",
            last_name="User",
            phone_number="+1234567890"
        )
        self.appt_date = datetime.now().date() + timedelta(days=2)
        self.appointment = AppointmentTable.objects.create(
            user=self.user,
            start_time=time(10, 0),
            end_time=time(10, 30),
            date=timezone.make_aware(datetime.combine(self.appt_date, time(0, 0))),
            location="Test Location"
        )

    def parse_twiml(self, response):
        return ET.fromstring(response.content.decode())

    @patch("admin_panel.views.phone_service_reschedule.generate_requested_date")
    def test_prompt_reschedule_appointment_over_one(self, mock_generate_requested_date):
        mock_generate_requested_date.return_value = None
        request = self.factory.post("/prompt_reschedule_appointment_over_one/", {"From": self.user.phone_number})
        response = prompt_reschedule_appointment_over_one(request)
        self.assertEqual(response.status_code, 200)
        root = self.parse_twiml(response)
        self.assertIn("Which appointment would you like to reschedule?", [say.text for say in root.iter("Say")])

    @patch("admin_panel.views.phone_service_reschedule.OpenAI")
    def test_generate_requested_date_valid(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="2025-04-02"))]
        )
        request = self.factory.post("/generate_requested_date/", {"SpeechResult": "Next Tuesday", "From": self.user.phone_number})
        response = generate_requested_date(request)
        self.assertEqual(response.status_code, 200)
        root = self.parse_twiml(response)
        self.assertIn("Your requested day was 2025-04-02. Is that correct?", [say.text for say in root.iter("Say")])

    def test_generate_requested_date_empty(self):
        request = self.factory.post("/generate_requested_date/", {"SpeechResult": "", "From": self.user.phone_number})
        response = generate_requested_date(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("/prompt_reschedule_appointment_over_one/", response.content.decode())

    @patch("admin_panel.views.phone_service_reschedule.get_response_sentiment", return_value=True)
    def test_confirm_requested_date_valid(self, mock_sentiment):
        date_str = self.appt_date.strftime("%Y-%m-%d")
        encoded = urllib.parse.quote(date_str)

        request = self.factory.post(f"/confirm_requested_date/{encoded}/", {
            "From": self.user.phone_number,
            "SpeechResult": "Yes"
        })

        response = confirm_requested_date(request, encoded)
        self.assertEqual(response.status_code, 200)

        decoded_xml = response.content.decode()
        self.assertIn(f"/reschedule_appointment/{encoded}/", decoded_xml)
        self.assertIn("<Redirect>", decoded_xml)

    @patch("admin_panel.views.phone_service_reschedule.get_response_sentiment", return_value=True)
    def test_confirm_requested_date_not_in_user_appointments(self, mock_sentiment):
        encoded = urllib.parse.quote("2025-12-31")
        request = self.factory.post(f"/confirm_requested_date/{encoded}/", {
            "From": self.user.phone_number,
            "SpeechResult": "Yes"
        })
        response = confirm_requested_date(request, encoded)
        self.assertEqual(response.status_code, 200)
        self.assertIn("this is not in your appointments", response.content.decode())

    @patch("admin_panel.views.phone_service_reschedule.get_response_sentiment", return_value=False)
    def test_confirm_requested_date_negative_response(self, mock_sentiment):
        encoded = urllib.parse.quote(self.appt_date.strftime("%Y-%m-%d"))
        request = self.factory.post(f"/confirm_requested_date/{encoded}/", {
            "From": self.user.phone_number,
            "SpeechResult": "No"
        })
        response = confirm_requested_date(request, encoded)
        self.assertEqual(response.status_code, 200)
        root = self.parse_twiml(response)
        self.assertEqual(root.tag, "Response")  # Confirm root TwiML response

    @patch("admin_panel.views.phone_service_reschedule.get_response_sentiment", return_value=True)
    def test_confirm_requested_date_invalid_date_format(self, mock_sentiment):
        invalid_encoded = urllib.parse.quote("Not-a-date")
        request = self.factory.post(f"/confirm_requested_date/{invalid_encoded}/", {
            "From": self.user.phone_number,
            "SpeechResult": "Yes"
        })
        response = confirm_requested_date(request, invalid_encoded)
        self.assertEqual(response.status_code, 200)
        self.assertIn("we could not understand the date", response.content.decode())

    @patch("admin_panel.views.phone_service_reschedule.generate_requested_date")
    def test_prompt_reschedule_appointment_over_one_spanish(self, mock_generate_req_date):
        """test spanish route for rescheduling when caller has more than one appointment scheduled"""
        self.user.language = "es"
        self.user.save()

        request = self.factory.post("/prompt_reschedule_appointment_over_one/", {"From": self.user.phone_number})
        response = prompt_reschedule_appointment_over_one(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Que cita le gustaria reprogramar?", response.content.decode())
    
    @patch("admin_panel.views.phone_service_reschedule.OpenAI")
    @patch("admin_panel.views.phone_service_reschedule.translate_to_language")
    def test_generate_requested_date_spanish(self, mock_translate, mock_openai):
        """test spanish route for appointment date generation on rescheduling path"""
        self.user.language = "es"
        self.user.save()
        mock_translate.return_value = "Su dia solicitado fue 2025-04-02. ¿Es correcto?"

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="2025-04-02"))]
        )
        request = self.factory.post("/generate_requested_date/", {"SpeechResult": "Quiero cambiar mi cita al dos de abril", "From": self.user.phone_number})
        response = generate_requested_date(request)

        self.assertEqual(response.status_code, 200)
        root = self.parse_twiml(response)
        self.assertTrue(any("Su dia solicitado fue 2025-04-02" in say.text for say in root.iter("Say")))
        
    @patch("admin_panel.views.phone_service_reschedule.get_response_sentiment")
    @patch("admin_panel.views.phone_service_reschedule.translate_to_language")
    def test_confirm_requested_date_spanish_correct(self, mock_translate, mock_sentiment):
        """test spanish route for confirmation on a valid appointment date"""
        self.user.language = "es"
        self.user.save()

        mock_sentiment.return_value = True
        mock_translate.return_value = "Yes"

        date_str = self.appt_date.strftime("%Y-%m-%d")
        encoded = urllib.parse.quote(date_str)

        request = self.factory.post(f"/confirm_requested_date/{encoded}/", {
            "From": self.user.phone_number,
            "SpeechResult": "Si"
        })
        response = confirm_requested_date(request, encoded)

        self.assertEqual(response.status_code, 200)
        self.assertIn("/reschedule_appointment/", response.content.decode())

    @patch("admin_panel.views.phone_service_reschedule.get_response_sentiment")
    @patch("admin_panel.views.phone_service_reschedule.translate_to_language")
    def test_confirm_requested_date_spanish_invalid(self, mock_translate, mock_sentiment):
        """test spanish route for confirmation on an invalid appointment date"""
        self.user.language = "es"
        self.user.save()
        mock_sentiment.return_value = True
        mock_translate.return_value = "Yes"

        future_date = (datetime.now().date() + timedelta(days=30)).strftime("%Y-%m-%d")
        encoded = urllib.parse.quote(future_date)

        request = self.factory.post(f"/confirm_requested_date/{encoded}/", {
            "From": self.user.phone_number,
            "SpeechResult": "Si"
        })
        response = confirm_requested_date(request, encoded)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Lo sentimos, esto no esta en tus citas.", response.content.decode())
