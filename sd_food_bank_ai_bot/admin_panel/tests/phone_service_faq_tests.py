from django.test import TestCase, Client, RequestFactory
from unittest.mock import patch, MagicMock
from admin_panel.views.phone_service_faq import *
from admin_panel.models import Log, FAQ
from django.http import HttpRequest
from django.urls import reverse
import urllib.parse
import datetime
import json


class TwilioViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
    
    def test_answer_call(self):
        """
        Test to make sure that answer_call view returns valid TwiML response.
        """
        response = self.client.get('/answer/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        # Check for expected greeting and the TwiML tags
        self.assertIn("Thank you for calling the San Diego Food Bank! Press 1 to\
         schedule an appointemnt, press 2 to reshedule and appointment,\
             press 3 to cancel an appointment, press 4 to ask about specific\
                inquires, or press 0 to be forwarded to an operator.", content)
        self.assertIn("<Response>", content)
        self.assertIn("</Response>", content)
    
    def test_answer_call_faq(self):
        """
        Test for when the user indicates they wish to ask a question.
        """
        request = self.factory.post("/get_question_from_user/", {"Digits": "4"})
        response = answer_call(request)

        self.assertIn("/prompt_question/", response.content.decode())
    
    def test_answer_call_schedule(self):
        """
        Test for when the user indicates they wish to schedule an appointment.
        """
        request = self.factory.post("/get_question_from_user/", {"Digits": "1"})
        response = answer_call(request)

        self.assertIn("/check_account/", response.content.decode())
    
    def test_answer_call_no_input(self):
        """
        Test for when the user gives no input.
        """
        request = self.factory.post("/get_question_from_user/", {})
        response = answer_call(request)

        self.assertNotIn("/check_account/", response.content.decode())
        self.assertNotIn("/prompt_question/", response.content.decode())


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


class PhoneFAQService(TestCase):
    def setUp(self):
        """Setup a test database with questions and answers"""
        self.factory = RequestFactory()
        self.faq_1 = FAQ.objects.create(question="When does the food bank open?",
                                        answer="The food bank is open Monday-Friday from 9:00 AM to 5:00 PM")
        self.faq_2 = FAQ.objects.create(question="How can I have access to the food bank client choice center?",
                                        answer="You must have an appointment.")
        self.faq_3 = FAQ.objects.create(question="How can I schedule an appointment?",
                                        answer="To schedule an appointment, visit calendly.com/sdfb.")
    
    @patch("admin_panel.views.phone_service_faq.get_matching_question")
    def test_get_question_from_user_valid(self, mock_get_matching_question):
        """Test for when a valid question is asked"""
        question = "When does the food bank open?"
        mock_get_matching_question.return_value = question # Avoids API call

        request = self.factory.post("/get_question_from_user/", {"SpeechResult": "What time do you open?"})
        response = get_question_from_user(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"You asked: {question} Is this correct?", response.content.decode())
    
    @patch("admin_panel.views.phone_service_faq.get_matching_question")
    def test_get_question_from_user_invalid(self, mock_get_matching_question):
        """Test for when a question did not match"""
        mock_get_matching_question.return_value = None

        request = self.factory.post("/get_question_from_user/", {"SpeechResult": "What time do you open?"})
        response = get_question_from_user(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Sorry, I don't have the answer to that at this time. Maybe try rephrasing your question.", response.content.decode())
    
    @patch("admin_panel.views.phone_service_faq.get_matching_question")
    def test_get_question_from_user_unheard(self, mock_get_matching_question):
        """Test for when the bot does not receive an input"""
        mock_get_matching_question.return_value = None

        request = self.factory.post("/get_question_from_user/", {"SpeechResult": ""})
        response = get_question_from_user(request)

        self.assertEqual(response.status_code, 200)
        mock_get_matching_question.assert_not_called()
        self.assertIn("Sorry, I couldn't understand that.", response.content.decode())
    
    def test_prompt_question(self):
        """Test for prompting the user for input"""
        self.client = Client()

        response = self.client.get(reverse("prompt_question"), follow=False)

        self.assertEqual(response.status_code, 200)
        self.assertIn("What can I help you with?", response.content.decode())
    
    @patch("admin_panel.views.phone_service_faq.get_response_sentiment")
    @patch("admin_panel.views.phone_service_faq.get_corresponding_answer")
    def test_confirm_question_affirmative(self, mock_get_corresponding_answer, mock_get_response_sentiment):
        """Test for when the user has said the question is correct"""
        mock_get_response_sentiment.return_value = True

        mock_get_corresponding_answer.return_value = "The food bank is open Monday-Friday from 9:00 AM to 5:00 PM"

        question = "When does the food bank open?"
        question_encoded = urllib.parse.quote(question)
        request = self.factory.post(f"/confirm_question/{question_encoded}/", {"SpeechResult": "Yes"})
        response = confirm_question(request, question_encoded)

        self.assertEqual(response.status_code, 200)
        self.assertIn("The food bank is open Monday-Friday from 9:00 AM to 5:00 PM", response.content.decode())
    
    @patch("admin_panel.views.phone_service_faq.get_response_sentiment")
    @patch("admin_panel.views.phone_service_faq.get_corresponding_answer")
    def test_confirm_question_operator(self, mock_get_corresponding_answer, mock_get_response_sentiment):
        """Test for when the user has said the question is correct and is asking for an operator"""
        mock_get_response_sentiment.return_value = True

        question = "Can I speak to an operator?"
        question_encoded = urllib.parse.quote(question)
        request = self.factory.post(f"/confirm_question/{question_encoded}/", {"SpeechResult": "Yes"})
        response = confirm_question(request, question_encoded)

        self.assertEqual(response.status_code, 200)
        self.assertIn("I'm transferring you to an operator now. Please hold.", response.content.decode())
        self.assertIn("###-###-####", response.content.decode())
    
    @patch("admin_panel.views.phone_service_faq.get_response_sentiment")
    def test_confirm_question_negative(self, mock_get_response_sentiment):
        """Test for when the user has said the question is incorrect"""
        mock_get_response_sentiment.return_value = False

        question = "When does the food bank open?"
        question_encoded = urllib.parse.quote(question)
        request = self.factory.post(f"/confirm_question/{question_encoded}/", {"SpeechResult": "Yes"})
        response = confirm_question(request, question_encoded)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Sorry about that. Please try asking again or rephrasing.", response.content.decode())
    
    @patch("admin_panel.views.phone_service_faq.get_response_sentiment")
    def test_confirm_question_unheard(self, mock_get_response_sentiment):
        """Test for when the bot receives no input"""
        mock_get_response_sentiment.return_value = False

        question = "When does the food bank open?"
        question_encoded = urllib.parse.quote(question)
        request = self.factory.post(f"/confirm_question/{question_encoded}/", {"SpeechResult": ""})
        response = confirm_question(request, question_encoded)

        mock_get_response_sentiment.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sorry, I couldn't understand that. Please try again.", response.content.decode())
    
    @patch("admin_panel.views.phone_service_faq.OpenAI")
    def test_get_matching_question_api_call(self, mock_openai):
        """Test for making sure api is called and response returned"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Prompt"))]
        )

        question = "When does the food bank open?"
        request = self.factory.post("/get_matching_question/")
        response = get_matching_question(request, question)

        mock_client.chat.completions.create.assert_called()
        self.assertEqual("Prompt", response)
    
    @patch("admin_panel.views.phone_service_faq.OpenAI")
    def test_get_matching_question_api_call(self, mock_openai):
        """Test for when api returns NONE"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="NONE"))]
        )

        question = "When does the food bank open?"
        request = self.factory.post("/get_matching_question/")
        response = get_matching_question(request, question)

        mock_client.chat.completions.create.assert_called()
        self.assertEqual(None, response)
    
    def test_get_corresponding_answer(self):
        """Test for correct answer returned"""
        question = "How can I schedule an appointment?"
        request = self.factory.post("/get_corresponding_answer/")
        response = get_corresponding_answer(request, question)

        answer = "To schedule an appointment, visit calendly.com/sdfb."
        self.assertEqual(response, answer)    