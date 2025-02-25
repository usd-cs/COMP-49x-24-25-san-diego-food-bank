from django.test import TestCase, Client
from admin_panel.models import Log
import json
import datetime


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