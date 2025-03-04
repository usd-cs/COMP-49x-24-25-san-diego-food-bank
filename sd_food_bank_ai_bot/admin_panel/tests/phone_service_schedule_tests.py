from django.test import TestCase, Client, RequestFactory

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
    
    def test_get_current_phone_number(self):
        phone_number = "+16192222222"
        
        request = self.factory.post("/get_current_phone_number", {"From": f"{phone_number}"})
        response = get_current_phone_number(request)
        
        self.assertEquals(phone_number, response.content.decode())