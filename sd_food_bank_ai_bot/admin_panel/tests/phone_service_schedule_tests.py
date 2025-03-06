from django.test import TestCase, RequestFactory
from admin_panel.views.phone_service_schedule import *


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