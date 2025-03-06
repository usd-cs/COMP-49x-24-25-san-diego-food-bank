from django.test import TestCase, Client, RequestFactory
from unittest.mock import patch, MagicMock
from admin_panel.views.phone_service_faq import *
from admin_panel.models import Log, FAQ, User
from django.http import HttpRequest
from django.urls import reverse
import urllib.parse
import datetime
import json
import xml.etree.ElementTree as ET



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
    
class PhoneSchedulingService(TestCase):
    def setUp(self):
        self.client = Client()
        self.test_user = User.objects.create(
            first_name="Billy",
            last_name="Bob",
            phone_number="+1234567890",
            email="billybob@email.com"
        )
    
    def test_check_account_found(self):
        """
        Test that when an account exists for the caller's number, the response
        contains their name and a confirmation.
        """
        response = self.client.post(
            reverse("check_account"),
            {"From": self.test_user.phone_number}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        root = ET.fromstring(content)
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)

        self.assertIn("Hello, Billy Bob", say_text)
        self.assertIn("Is this your account?", say_text)
    
    def test_check_account_not_found(self):
        """
        Test that when no account exists for the phone number, the response
        informs the caller.
        """
        response = self.client.post(
            reverse("check_account"),
            {"From": "+1987654321"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = ET.fromstring(content)
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("We did not find an account", say_text)
    
    def test_confirm_account_yes(self):
        """
        Test that when the caller confirms by saying "yes", the response 
        will confirm the account.
        """
        response = self.client.post(
            reverse("confirm_account"),
            {"SpeechResult": "Yes, that's correct"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = ET.fromstring(content)
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("Your account has been confirmed!", say_text)
    
    def test_confirm_account_no(self):
        """
        Test that when the caller confirms by saying "no", the response 
        will encourage them to try again.
        """
        response = self.client.post(
            reverse("confirm_account"),
            {"SpeechResult": "No, that's not right"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        root = ET.fromstring(content)
        say_text = " ".join(elem.text for elem in root.iter("Say") if elem.text)
        self.assertIn("I'm sorry, please try again.", say_text)
    
    