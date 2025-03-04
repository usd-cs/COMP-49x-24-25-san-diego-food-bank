from django.test import TestCase, Client, RequestFactory
from admin_panel.views.phone_service_schedule import *
from unittest.mock import patch, MagicMock
from django.http import HttpResponse


class RequestPhoneNumberTests(TestCase):
    def setUp(self):
        """Setup a request facotry for use during tests"""
        self.factory = RequestFactory()
    
    def test_get_phone_number(self):
        """Test the first prompt for getting a users phone number"""
        self.client = Client()
        response = self.client.get("/get_phone_number")
        content = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn("Would you like to use the number you're calling from, or provide a different one?", content)

    @patch("admin_panel.views.phone_service_schedule.OpenAI")
    @patch("admin_panel.views.phone_service_schedule.get_current_phone_number")
    @patch("admin_panel.views.phone_service_schedule.get_other_phone_number")
    def test_get_user_phone_preference_current(self, mock_get_other_phone_number, mock_get_current_phone_number, mock_openai):
        """Test when the user responds with wanting to use their current phone number."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="CURRENT"))]
        )

        mock_get_other_phone_number.return_value("+16293641295")
        mock_get_current_phone_number.return_value("+29999999999")
        request = self.factory.post("/get_user_phone_preference/") # used only as parameter

        ret_value = get_user_phone_preference(request, "tmp")

        mock_get_other_phone_number.assert_not_called
        mock_get_current_phone_number.assert_called()
        self.assertEqual(ret_value, "+29999999999")

    @patch("admin_panel.views.phone_service_schedule.OpenAI")
    @patch("admin_panel.views.phone_service_schedule.get_current_phone_number")
    @patch("admin_panel.views.phone_service_schedule.get_other_phone_number")
    def test_get_user_phone_preference_other(self, mock_get_other_phone_number, mock_get_current_phone_number, mock_openai):
        """Test when the user responds with wanting to use a different phone number."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="OTHER"))]
        )

        mock_get_other_phone_number.return_value("+16293641295")
        mock_get_current_phone_number.return_value("+29999999999")
        request = self.factory.post("/get_user_phone_preference/") # used only as parameter

        ret_value = get_user_phone_preference(request, "tmp")

        mock_get_other_phone_number.assert_called
        mock_get_current_phone_number.assert_not_called()
        self.assertEqual(ret_value, "+16293641295")
    
    """
    def test_get_current_phone_number(self):
        phone_number = "+16192222222"
        
        request = self.factory.post("/get_current_phone_number/", {"From": f"{phone_number}"})
        response = get_current_phone_number(request)
        
        self.assertIn(phone_number, response.content.decode())
    """