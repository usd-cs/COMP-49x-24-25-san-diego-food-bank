from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from admin_panel.models import Admin, FAQ, Tag, Log
import json
import datetime
from datetime import datetime, timedelta
from unittest.mock import patch

class LoginViewsTestCase(TestCase):
    def setUp(self):
        """Set up a test client & user"""
        self.client = Client()
        self.admin = Admin.objects.create_user(username='user1', password='pass123')

    def test_get_request(self):
        """Test the GET request for the login view"""
        response = self.client.get(reverse('login'))  # Make sure the URL works
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')

    def test_post_request(self):
        """Test the POST request with valid login credentials"""
        response = self.client.post(reverse('login'), {'username': 'user1', 'password': 'pass123'})
        self.assertEqual(response.status_code, 302)

    def test_post_invalid_user(self):
        """Test the POST request with invalid login credentials"""
        response = self.client.post(reverse('login'), {'username': 'user3', 'password': 'pass321'})
        self.assertTemplateUsed(response, 'login.html')


class LogoutViewTestCase(TestCase):
    def setUp(self):
        """Set up test client and a user"""
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='testpassword')

    def test_logout_redirect(self):
        """Test that the logout view redirects back to login page"""
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('login'))

    def test_user_logged_out(self):
        """Test to make sure the user is logged out"""
        self.client.login(username='testuser', password='testpassword')
        self.client.get(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)  # There should be no user id in the session


class FAQPageTestCase(TestCase):
    def setUp(self):
        """Set up a test client and FAQ objects"""
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='testpassword')

        self.faq_1 = FAQ.objects.create(question="When does the food bank open?",
                                        answer="The food bank is open Monday-Friday from 9:00 AM to 5:00 PM")
        self.faq_2 = FAQ.objects.create(question="How can I have access to the food bank client choice center?",
                                        answer="You must have an appointment.")
        self.tag_1 = Tag.objects.create(name="Hours")
        self.tag_2 = Tag.objects.create(name="Access")
        self.faq_1.tags.add(self.tag_1)
        self.faq_2.tags.add(self.tag_2)

    def test_get_request(self):
        """Test the GET request for FAQ view"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('faq_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'faq_page.html')

    def test_items_displayed(self):
        """Test all items being displayed when not searching"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('faq_page'))

        # Check first FAQ appears
        self.assertContains(response, "When does the food bank open?")
        self.assertContains(response, "The food bank is open Monday-Friday from 9:00 AM to 5:00 PM")

        # Check second FAQ appears
        self.assertContains(response, "How can I have access to the food bank client choice center?")
        self.assertContains(response, "You must have an appointment.")

    def test_delete_faq(self):
        """Test deleting an FAQ"""
        # Verify the FAQ exists initially
        self.assertTrue(FAQ.objects.filter(id=self.faq_1.id).exists())

        # Send POST request to delete the FAQ
        self.client.force_login(self.user)
        response = self.client.post(reverse('delete_faq', args=[self.faq_1.id]))

        # Check redirection after deletion
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('faq_page'))

        # Verify the FAQ no longer exists in the database
        self.assertFalse(FAQ.objects.filter(id=self.faq_1.id).exists())

        # Check if the FAQ is no longer displayed on the page
        response = self.client.get(reverse('faq_page'))
        self.assertNotContains(response, "When does the food bank open?")
        self.assertNotContains(response, "The food bank is open Monday-Friday from 9:00 AM to 5:00 PM")

    def test_add_valid_faq(self):
        """Test adding a valid FAQ"""
        faq_info = {
            'question': 'What do you sell?',
            'answer': 'We sell food of all kinds.',
            'existing_tags': [self.tag_1.id, self.tag_2.id],
            'new_tags': 'Products',
        }

        self.client.force_login(self.user)

        response = self.client.post(reverse('create_faq'), faq_info)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('faq_page'))

        faq = FAQ.objects.get(question='What do you sell?')
        self.assertIsNotNone(faq)
        self.assertEqual(faq.question, 'What do you sell?')
        self.assertEqual(faq.answer, 'We sell food of all kinds.')
        self.assertEqual(faq.tags.count(), 3)

    def test_add_invalid_faq(self):
        """Test adding an invalid FAQ"""
        faq_info = {
            'question': '',
            'answer': '',
            'existing_tags': [self.tag_1.id, self.tag_2.id],
            'new_tags': 'Products',
        }
        self.client.force_login(self.user)

        response = self.client.post(reverse('create_faq'), faq_info)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(FAQ.objects.filter(question='').exists())

    def test_edit_faq(self):
        """Test editing already existing FAQ"""
        self.client.force_login(self.user)
        faq = FAQ.objects.get(question="When does the food bank open?")
        new_faq_info = {
            'question': 'What do you sell?',
            'answer': 'We sell food of all kinds.',
            'existing_tags': [self.tag_1.id, self.tag_2.id],
            'new_tags': 'Products',
        }

        response = self.client.post(reverse('edit_faq', args=[faq.id]), new_faq_info)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('faq_page'))

        faq.refresh_from_db()

        self.assertEqual(faq.question, 'What do you sell?')
        self.assertEqual(faq.answer, 'We sell food of all kinds.')
        self.assertEqual(faq.tags.count(), 3)

    def test_search_no_results(self):
        """Test no search results when searching for a string not in any questions/answers"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('faq_page'), {'q': "asdfasdfasdfasdf"})
        self.assertNotContains(response, "When does the food bank open?")
        self.assertNotContains(response, "How can I have access to the food bank client choice center?")
        self.assertContains(response, "No matching entries found")

    def test_search_with_results(self):
        """Test the correct item is displayed when searching for a string in a question/answer"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('faq_page'), {'q': "appointment"})
        self.assertContains(response, "How can I have access to the food bank client choice center?")
        self.assertNotContains(response, "When does the food bank open?")

    def test_tag_filter_hours(self):
        """Test filtering by 'Hours' tag"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('faq_page'), {'tag': self.tag_1.id})
        self.assertContains(response, "When does the food bank open?")
        self.assertNotContains(response, "How can I have access to the food bank client choice center?")

    def test_tag_filter_access(self):
        """Test filtering by 'Access' tag"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('faq_page'), {'tag': self.tag_2.id})
        self.assertContains(response, "How can I have access to the food bank client choice center?")
        self.assertNotContains(response, "When does the food bank open?")

    def test_tag_filter_all_tags(self):
        """Test displaying all FAQs when no tag is selected"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('faq_page'))
        self.assertContains(response, "When does the food bank open?")
        self.assertContains(response, "How can I have access to the food bank client choice center?")

class TwilioViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client() 
    
    def test_answer_call(self):
        """
        Test to make sure that answer_call view returns valid TwiML response.
        """
        response = self.client.get('/answer/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        # Check for expected greeting and the TwiML tags
        self.assertIn("Thank you for calling!", content)
        self.assertIn("<Response>", content)
        self.assertIn("</Response>", content)

    def test_twilio_webhook_invalid(self):
        """
        Test that a non-POST request will return a 405 error code.
        """
        response = self.client.get('/twilio_webhook/')
        self.assertEqual(response.status_code, 405)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data.get('error'), "Method not allowed")

    def test_twilio_webhook_faq_query(self):
        """
        Test that a valid POST with the CurrentTask 'faq_query' returns the proper action.
        """
        # Payload defined with the faq_query task and a sample user input
        payload = {
            "CurrentTask": "faq_query",
            "Field": { "user_input": "What are your operating hours?"}
        }
        # Simulating the POST request to the twilio webhook endpoint with json data
        response = self.client.post(
            '/twilio_webhook/',
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        self.assertIn("actions", data)
        actions = data["actions"]
        self.assertIsInstance(actions, list) # Assert that "actions" is a list 

        confirmation = any(action.get("say") == "Did that answer your question?" for action in actions)
        self.assertTrue(confirmation)
        # Make sure there is a listen action 
        listen = any(action.get("listen") is True for action in actions)
        self.assertTrue(listen)
    
    def test_twilio_webhook_unrecognized_task(self):
        """
        Test to makre sure a POST with an unrecognized CurrentTask returns default error action.
        """
        # Defined the payload with an unrecognized task and sample user input
        payload = {
            "CurrentTask": "unknown_task",
            "Field": {"user_input": "Billy Bob Joe"}
        }
        response = self.client.post(
            '/twilio_webhook/',
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        self.assertIn("actions", data)
        actions = data["actions"]
        self.assertIsInstance(actions, list)

        default_message_found = any("I didn't understand" in action.get("say", "") for action in actions)
        self.assertTrue(default_message_found)
        # Make sure there is at least one action telling the bot to listen for further input
        listen = any(action.get("listen") is True for action in actions)
        self.assertTrue(listen)

    def test_text_to_speech_invalid_json(self):
        """
        Test that an invalid JSON payload returns a 400 error.
        """
        response = self.client.post(
            "/text_to_speech/", 
            data="not json", 
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode("utf-8"))
        self.assertEqual(data.get("error"), "Invalid JSON payload")
    
    def test_text_to_speech_invalid_method(self):
        """
        Test that a non-POST request returns a 405 error.
        """
        response = self.client.get("/text_to_speech/")
        self.assertEqual(response.status_code, 405)
        data = json.loads(response.content.decode("utf-8"))
        self.assertEqual(data.get("error"), "Method not allowed")

class LogModelTestCase(TestCase):
    def setUp(self):
        self.log = Log.objects.create(
            phone_number = "+1111111111",
            transcript = [
                {"speaker": "caller", "message": "Question!"},
                {"speaker": "bot", "message": "Response!"}
            ],
            length_of_call = datetime.timedelta(minutes = 4, seconds = 18),
            strikes = 0,
            intents = {"schedule": 1}
        )
    
    def test_add_intent(self):
        """Test valid addition and counting of new and/or already existing intents throughout a call's dialogue"""
        expected_intent_dict = {"schedule": 1,
                                "working hours": 2}
        
        self.log.add_intent("working hours")
        self.assertEqual(self.log.intents["working hours"], 1)
        
        self.log.add_intent("working hours")
        self.assertEqual(self.log.intents["working hours"], 2)

        self.assertEqual(self.log.intents, expected_intent_dict)

    def test_add_strike(self):
        """Test correct tracking for the strike system prior to forwarding caller to an operator"""
        self.assertEqual(self.log.strikes, 0)

        forward = self.log.add_strike()
        self.assertEqual(self.log.strikes, 1)
        self.assertFalse(forward)

        forward = self.log.add_strike()
        self.assertEqual(self.log.strikes, 2)
        self.assertTrue(forward)


    def test_add_message(self):
        """Test valid appending of dialogue to storage as call progresses between caller and bot"""
        self.log.add_transcript("caller", "Question 2!")

        expected_transcript = [
            {"speaker": "caller", "message": "Question!"},
            {"speaker": "bot", "message": "Response!"},
            {"speaker": "caller", "message": "Question 2!"}
        ]

        self.assertEqual(self.log.transcript, expected_transcript)

# class CallStatusUpdateTestCase(TestCase):

#     def setUp(self):
#         """Set up a test client and create a test Log object"""
#         self.client = self.client
#         self.phone_number = "+1234567890"
#         self.log = Log.objects.create(
#             phone_number=self.phone_number,
#             time_started=datetime.now() - timedelta(minutes=10),  # Assume the call started 10 minutes ago
#             length_of_call=None,
#             strikes=0,
#             intents={"operator": 1}
#         )

#     def test_post_call_completed(self):
#         """Test POST request with CallStatus 'completed'"""
#         # Simulate POST request with 'completed' status
#         data = {
#             'CallStatus': 'completed',
#             'From': self.phone_number,
#         }
        
#         response = self.client.post(reverse('call_status_update'), data)
        
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(response.json().get('status'), "success")

#         # Fetch the log object to verify time_ended and length_of_call
#         log = Log.objects.get(phone_number=self.phone_number)
        
#         # Ensure time_ended is updated
#         self.assertIsNotNone(log.time_ended)

#         # Ensure call duration is calculated
#         self.assertIsNotNone(log.length_of_call)
#         self.assertEqual(log.length_of_call, timedelta(minutes=10))  # Duration should be around 10 minutes

#     def test_post_invalid_call_status(self):
#         """Test POST request with CallStatus other than 'completed'"""
#         # Simulate POST request with a status other than 'completed'
#         data = {
#             'CallStatus': 'busy',  # Invalid status
#             'From': self.phone_number,
#         }

#         response = self.client.post(reverse('call_status_update'), data)
        
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(response.json().get('status'), "success")
        
#         # No changes should have occurred to the log (e.g., time_ended should still be None)
#         log = Log.objects.get(phone_number=self.phone_number)
#         self.assertIsNone(log.time_ended)
#         self.assertIsNone(log.length_of_call)

#     def test_invalid_method(self):
#         """Test that a non-POST request returns a 405 error"""
#         # Simulate GET request (should be a POST request)
#         response = self.client.get(reverse('call_status_update'))

#         self.assertEqual(response.status_code, 405)
#         data = json.loads(response.content.decode('utf-8'))
#         self.assertEqual(data.get("error"), "Method not allowed")
    
#     def test_missing_data(self):
#         """Test that missing data returns the correct error"""
#         # Simulate POST request without necessary data ('CallStatus' or 'From')
#         response = self.client.post(reverse('call_status_update'), {})
#         self.assertEqual(response.status_code, 200)  # Should still return success
#         data = json.loads(response.content.decode('utf-8'))
#         self.assertEqual(data.get("status"), "success")

class SpeechToTextTestCase(TestCase):

    def setUp(self):
        """Set up a test client"""
        self.client = self.client

    def test_speech_to_text_get_request(self):
        """Test the GET request for speech_to_text view"""
        response = self.client.get(reverse('speech_to_text'))
        
        # Check that the response status code is 200
        self.assertEqual(response.status_code, 200)
        
        # Parse the returned response (TwiML) to check for correctness
        content = response.content.decode('utf-8')
        
        # Check if the response contains the expected TwiML tags
        self.assertIn("<Response>", content)
        self.assertIn("</Response>", content)
        self.assertIn("<Say>", content)
        self.assertIn("Thank you for calling!", content)  # Check the greeting message
        self.assertIn("<Gather>", content)  # Ensure that the <Gather> tag is present
        self.assertIn('action="/get_question_from_user/"', content)  # Check the action URL for the Gather
        
        # Check if the Gather prompt is correct
        self.assertIn("What can I help you with?", content)

    @patch('twilio.twiml.voice_response.VoiceResponse')
    def test_speech_to_text_twilio_response(self, MockVoiceResponse):
        """Test the correct creation of TwiML response"""
        # Mock the VoiceResponse
        mock_response = MockVoiceResponse.return_value
        mock_response.say("Thank you for calling!")
        
        # Simulate the function call
        response = self.client.get(reverse('speech_to_text'))

        # Check if the VoiceResponse was correctly generated
        mock_response.say.assert_called_with("Thank you for calling!")

        # Check if the gather method is called with the correct arguments
        gather = mock_response.gather.return_value
        gather.say.assert_called_with("What can I help you with?")

    def test_invalid_method(self):
        """Test that a non-POST request returns a 405 error"""
        # Simulate a GET request (since speech_to_text expects a GET request)
        response = self.client.get(reverse('speech_to_text'))
        self.assertEqual(response.status_code, 200)  # Expect 200 for successful response

class OperatorViewTestCase(TestCase):

    @patch('twilio.twiml.voice_response.VoiceResponse.say')
    @patch('twilio.twiml.voice_response.VoiceResponse.dial')
    def test_operator_call_forwarding(self, MockVoiceResponse):
        """Test that the operator function returns the correct TwiML response."""
        
        # Create a mock of the VoiceResponse object
        mock_response = MockVoiceResponse.return_value
        mock_response.say("Now forwarding to operator. Please hold.")
        
        # Simulate the function call
        response = self.client.get(reverse('operator'))  # Assuming the URL name is 'operator'

        # Ensure the response status is 200 (successful)
        self.assertEqual(response.status_code, 200)

        # Check that the VoiceResponse's 'say' method was called with the correct message
        mock_response.say.assert_called_with("Now forwarding to operator. Please hold.")

        # Check that the dial method was called and contains the operator's phone number
        dial = mock_response.dial.return_value
        dial.number.assert_called_with('+17028586982')  # Replace with actual operator's phone number

        # Ensure the response contains valid TwiML structure
        content = response.content.decode('utf-8')
        self.assertIn("<Response>", content)
        self.assertIn("</Response>", content)
        self.assertIn("<Say>", content)
        self.assertIn("Now forwarding to operator. Please hold.", content)
        self.assertIn("<Dial>", content)
        self.assertIn("<Number>", content)  # Ensure <Number> tag for operator's number is present

    def test_operator_invalid_method(self):
        """Test that the operator view only accepts GET requests"""
        # Simulate a POST request
        response = self.client.post(reverse('operator'))
        self.assertEqual(response.status_code, 405)  # Should return 405 Method Not Allowed