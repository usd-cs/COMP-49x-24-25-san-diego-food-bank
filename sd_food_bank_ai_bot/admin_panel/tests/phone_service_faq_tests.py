from django.test import TestCase, Client, RequestFactory
from unittest.mock import patch, MagicMock
from admin_panel.views.phone_service_faq import (answer_call, confirm_question, get_matching_question,
                                                 get_question_from_user, strike_system_handler,
                                                 get_corresponding_answer, prompt_post_answer,
                                                 process_post_answer)
from admin_panel.models import Log, FAQ, User
from django.urls import reverse
from django.utils import timezone
import time
import urllib.parse
import datetime
from datetime import timedelta
import re


class TwilioViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.phone_number = "+17601231234"

        self.user, _ = User.objects.get_or_create(
            phone_number=self.phone_number,
            defaults={"first_name": "NaN", "last_name": "NaN"}
        )

        self.user2, _ = User.objects.get_or_create(
            phone_number="+17603214321",
            language="es",
            defaults={"first_name": "NaN", "last_name": "NaN"}
        )

        self.log = Log.objects.create(
            phone_number=self.phone_number,
            time_started=timezone.now()
        )

        self.log = Log.objects.create(
            phone_number="+17603214321",
            time_started=timezone.now()
        )

    def test_answer_call_english(self):
        """
        Test to make sure that answer_call view returns valid TwiML response in english.
        """
        content = {"From": "+17601231234"}
        response = self.client.post('/answer/', content)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        # Check for expected greeting and the TwiML tags
        msg = "press 1 to schedule an appointment, press 2 to reschedule an appointment,\
                    press 3 to cancel an appointment, press 4 to ask about specific inquiries,\
                    or press 5 to be forwarded to an operator."
        msg = re.sub(r"\s+", " ", msg)
        content = re.sub(r"\s+", " ", content)
        self.assertIn(msg, content)
        self.assertIn("<Response>", content)
        self.assertIn("</Response>", content)
        self.assertEqual(User.objects.get(phone_number="+17601231234").language, "en")

    def test_changing_language(self):
        """
        Test to make sure that the language is changed in answer.
        """
        content = {"Digits": "0", "From": "+17601231234"}
        response = self.client.post('/answer/', content)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertEqual(User.objects.get(phone_number="+17601231234").language, "es")

    def test_answer_call_spanish(self):
        """
        Test to make sure that answer_call view returns valid TwiML response in spanish.
        """
        content = {"From": "+17603214321"}
        response = self.client.post('/answer/', content)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Check for expected greeting and the TwiML tags
        self.assertIn("For english press 0.", content)
        self.assertIn("<Response>", content)
        self.assertIn("</Response>", content)

    def test_answer_call_faq(self):
        """
        Test for when the user indicates they wish to ask a question.
        """
        request = self.factory.post("/get_question_from_user/", {"Digits": "4", "From": "+17601231234"})
        response = answer_call(request)

        self.assertIn("/prompt_question/", response.content.decode())

    def test_answer_call_schedule(self):
        """
        Test for when the user indicates they wish to schedule an appointment.
        """
        request = self.factory.post("/get_question_from_user/", {"Digits": "1", "From": "+17601231234"})
        response = answer_call(request)

        self.assertIn("/check_account/", response.content.decode())

    def test_answer_call_no_input(self):
        """
        Test for when the user gives no input.
        """
        request = self.factory.post("/get_question_from_user/", {"From": "+17601231234"})
        response = answer_call(request)

        self.assertNotIn("/check_account/", response.content.decode())
        self.assertNotIn("/prompt_question/", response.content.decode())
        self.assertIn("/answer/", response.content.decode())


class LogModelTestCase(TestCase):
    def setUp(self):
        self.log = Log.objects.create(
            phone_number="+1111111111",
            transcript=[
                {"speaker": "caller", "message": "Question!"},
                {"speaker": "bot", "message": "Response!"}
            ],
            length_of_call=datetime.timedelta(minutes=4, seconds=18),
            strikes=0,
            intents={"schedule": 1}
        )

    def test_add_intent(self):
        """Test valid addition and counting of new and/or already existing
        intents throughout a call's dialogue"""
        expected_intent_dict = {"schedule": 1,
                                "working hours": 2}

        self.log.add_intent("working hours")
        self.assertEqual(self.log.intents["working hours"], 1)

        self.log.add_intent("working hours")
        self.assertEqual(self.log.intents["working hours"], 2)

        self.assertEqual(self.log.intents, expected_intent_dict)

    def test_add_strike(self):
        """Test correct tracking for the strike system prior to forwarding
        caller to an operator"""
        self.assertEqual(self.log.strikes, 0)

        forward = self.log.add_strike()
        self.assertEqual(self.log.strikes, 1)
        self.assertFalse(forward)

        forward = self.log.add_strike()
        self.assertEqual(self.log.strikes, 2)
        self.assertTrue(forward)

    def test_add_message(self):
        """Test valid appending of dialogue to storage as call progresses
        between caller and bot"""
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
        
        self.user_eng = User.objects.create(first_name="John", last_name="Doe", phone_number="+17601231234")
        self.user_span = User.objects.create(first_name="Jane", last_name="Doe", phone_number="+17603214321", language="es")

    @patch("admin_panel.views.phone_service_faq.get_matching_question")
    def test_get_question_from_user_valid(self, mock_get_matching_question):
        """Test for when a valid question is asked"""
        question = "When does the food bank open?"
        mock_get_matching_question.return_value = question  # Avoids API call

        request = self.factory.post("/get_question_from_user/",
                                    {"SpeechResult": "What time do you open?",
                                     "From": "+17601231234"})
        response = get_question_from_user(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"You asked: {question} Is this correct?",
                      response.content.decode())
    
    @patch("admin_panel.views.phone_service_faq.get_matching_question")
    @patch("admin_panel.views.phone_service_faq.translate_to_language")
    def test_get_question_from_user_valid_spanish(self, mock_translate_to_language, mock_get_matching_question):
        """Test for when a valid question is asked in Spanish"""
        question = "¿Cuándo abre el banco de alimentos?"
        mock_translate_to_language.return_value = "Translated to Spanish"
        mock_get_matching_question.return_value = question  # Avoids API call

        request = self.factory.post("/get_question_from_user/",
                                    {"SpeechResult": "¿Cuándo abre el banco de alimentos?",
                                     "From": "+17603214321"})
        response = get_question_from_user(request)

        mock_translate_to_language.assert_called()
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"Preguntaste: Translated to Spanish",
                      response.content.decode())

    @patch("admin_panel.views.phone_service_faq.get_matching_question")
    def test_get_question_from_user_invalid(self, mock_get_matching_question):
        """Test for when a question did not match"""
        mock_get_matching_question.return_value = None

        request = self.factory.post("/get_question_from_user/",
                                    {"SpeechResult": "What time do you open?",
                                     "From": "+17601231234"})
        response = get_question_from_user(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Sorry, I don't have the answer to that at this time. Maybe try rephrasing your question.", response.content.decode())

    @patch("admin_panel.views.phone_service_faq.get_matching_question")
    @patch("admin_panel.views.phone_service_faq.translate_to_language")
    def test_get_question_from_user_invalid_spanish(self, mock_translate_to_language, mock_get_matching_question):
        """Test for when a question did not match in Spanish"""
        mock_translate_to_language.return_value = "Translated to Spanish"
        mock_get_matching_question.return_value = None  # Avoids API call

        request = self.factory.post("/get_question_from_user/",
                                    {"SpeechResult": "¿Cuándo abre el banco de alimentos?",
                                     "From": "+17603214321"})
        response = get_question_from_user(request)

        mock_translate_to_language.assert_called() # To translate asked question to english
        self.assertEqual(response.status_code, 200)
        self.assertIn("Lo siento, no tengo la respuesta en este momento.",
                      response.content.decode())

    @patch("admin_panel.views.phone_service_faq.get_matching_question")
    def test_get_question_from_user_unheard(self, mock_get_matching_question):
        """Test for when the bot does not receive an input"""
        mock_get_matching_question.return_value = None

        request = self.factory.post("/get_question_from_user/", {"SpeechResult": "",
                                                                 "From": "+17601231234"})
        response = get_question_from_user(request)

        self.assertEqual(response.status_code, 200)
        mock_get_matching_question.assert_not_called()
        self.assertIn("Sorry, I couldn't understand that.", response.content.decode())

    @patch("admin_panel.views.phone_service_faq.get_matching_question")
    @patch("admin_panel.views.phone_service_faq.translate_to_language")
    def  test_get_question_from_user_unheard_spanish(self, mock_translate_to_language, mock_get_matching_question):
        """Test for when the bot does not receive an input in Spanish"""
        mock_translate_to_language.return_value = "Translated to Spanish"
        mock_get_matching_question.return_value = None  # Avoids API call

        request = self.factory.post("/get_question_from_user/",
                                    {"SpeechResult": "",
                                     "From": "+17603214321"})
        response = get_question_from_user(request)

        mock_translate_to_language.assert_not_called()
        mock_get_matching_question.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Lo siento, no pude entender eso.",
                      response.content.decode())

    def test_prompt_question_english(self):
        """Test for prompting the user for input in English"""
        self.client = Client()

        content = {"From": "+17601231234"}
        response = self.client.post(reverse("prompt_question"), content, follow=False)

        self.assertEqual(response.status_code, 200)
        self.assertIn("What can I help you with?", response.content.decode())
    
    def test_prompt_question_spanish(self):
        """Test for prompting the user for input in Spanish"""
        self.client = Client()

        content = {"From": "+17603214321"}
        response = self.client.post(reverse("prompt_question"), content, follow=False)

        self.assertEqual(response.status_code, 200)
        # Can't give full sentence because of encoding of special symbols
        self.assertIn("puedo ayudarte?", response.content.decode())

    @patch("admin_panel.views.phone_service_faq.get_response_sentiment")
    @patch("admin_panel.views.phone_service_faq.get_corresponding_answer")
    def test_confirm_question_affirmative(self, mock_get_corresponding_answer,
                                          mock_get_response_sentiment):
        """Test for when the user has said the question is correct"""
        mock_get_response_sentiment.return_value = True

        mock_get_corresponding_answer.return_value = "The food bank is open Monday-Friday from 9:00 AM to 5:00 PM"

        question = "When does the food bank open?"
        question_encoded = urllib.parse.quote(question)
        request = self.factory.post(f"/confirm_question/{question_encoded}/", {"SpeechResult": "Yes",
                                                                               "From": "+17601231234"})
        response = confirm_question(request, question_encoded)

        self.assertEqual(response.status_code, 200)
        self.assertIn("The food bank is open Monday-Friday from 9:00 AM to 5:00 PM", response.content.decode())
        self.assertIn("/prompt_post_answer/", response.content.decode())
    
    @patch("admin_panel.views.phone_service_faq.get_response_sentiment")
    @patch("admin_panel.views.phone_service_faq.translate_to_language")
    def test_confirm_question_affirmative_spanish(self, mock_translate_to_language,
                                          mock_get_response_sentiment):
        """Test for when the user has said the question is correct in Spanish"""
        mock_get_response_sentiment.return_value = True
        mock_translate_to_language.return_value = "Translated to Spanish"

        question = "When does the food bank open?" # In English because passed as parameter from other function
        question_encoded = urllib.parse.quote(question)
        request = self.factory.post(f"/confirm_question/{question_encoded}/", {"SpeechResult": "Sí",
                                                                               "From": "+17603214321"})
        response = confirm_question(request, question_encoded)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Translated to Spanish", response.content.decode())
        self.assertIn("/prompt_post_answer/", response.content.decode())

    @patch("admin_panel.views.phone_service_faq.get_response_sentiment")
    @patch("admin_panel.views.phone_service_faq.get_corresponding_answer")
    def test_confirm_question_operator(self, mock_get_corresponding_answer, mock_get_response_sentiment):
        """Test for when the user has said the question is correct and is asking for an operator"""
        mock_get_response_sentiment.return_value = True

        question = "Can I speak to an operator?"
        question_encoded = urllib.parse.quote(question)
        request = self.factory.post(f"/confirm_question/{question_encoded}/", {"SpeechResult": "Yes",
                                                                               "From": "+17601231234"})
        response = confirm_question(request, question_encoded)

        self.assertEqual(response.status_code, 200)
        self.assertIn("I'm transferring you to an operator now. Please hold.",
                      response.content.decode())
        self.assertIn("###-###-####", response.content.decode())

    @patch("admin_panel.views.phone_service_faq.get_response_sentiment")
    def test_confirm_question_negative(self, mock_get_response_sentiment):
        """Test for when the user has said the question is incorrect"""
        mock_get_response_sentiment.return_value = False

        question = "When does the food bank open?"
        question_encoded = urllib.parse.quote(question)
        request = self.factory.post(f"/confirm_question/{question_encoded}/", {"SpeechResult": "No",
                                                                               "From": "+17601231234"})
        response = confirm_question(request, question_encoded)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Sorry about that. Please try asking again or rephrasing.", response.content.decode())
    
    @patch("admin_panel.views.phone_service_faq.get_response_sentiment")
    @patch("admin_panel.views.phone_service_faq.translate_to_language")
    def test_confirm_question_negative_spanish(self, mock_translate_to_language, mock_get_response_sentiment):
        """Test for when the user has said the question is incorrect in spanish"""
        mock_translate_to_language.return_vaue = "Translated to Spanish"
        mock_get_response_sentiment.return_value = False

        question = "When does the food bank open?" # Passed as parameter from a different function, so in English
        question_encoded = urllib.parse.quote(question)
        request = self.factory.post(f"/confirm_question/{question_encoded}/", {"SpeechResult": "No",
                                                                               "From": "+17603214321"})
        response = confirm_question(request, question_encoded)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Lo siento. Intenta preguntar de nuevo o reformula tu pregunta.", response.content.decode())

    @patch("admin_panel.views.phone_service_faq.get_response_sentiment")
    @patch("admin_panel.views.phone_service_faq.translate_to_language")
    def test_confirm_question_unheard_spanish(self, mock_translate_to_language, mock_get_response_sentiment):
        """Test for when the bot receives no input"""
        mock_translate_to_language.return_value = "Translated to Spanish"
        mock_get_response_sentiment.return_value = False

        question = "When does the food bank open?" # In English because previously translated
        question_encoded = urllib.parse.quote(question)
        request = self.factory.post(f"/confirm_question/{question_encoded}/", {"SpeechResult": "",
                                                                               "From": "+17603214321"})
        response = confirm_question(request, question_encoded)

        mock_get_response_sentiment.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Lo siento, no pude entender eso.", response.content.decode())

    @patch("admin_panel.views.phone_service_faq.get_response_sentiment")
    def test_confirm_question_unheard(self, mock_get_response_sentiment):
        """Test for when the bot receives no input"""
        mock_get_response_sentiment.return_value = False

        question = "When does the food bank open?"
        question_encoded = urllib.parse.quote(question)
        request = self.factory.post(f"/confirm_question/{question_encoded}/", {"SpeechResult": "",
                                                                               "From": "+17601231234"})
        response = confirm_question(request, question_encoded)

        mock_get_response_sentiment.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sorry, I couldn't understand that. Please try again.", response.content.decode())

    @patch("admin_panel.views.utilities.OpenAI")
    def test_get_matching_question_api_call(self, mock_openai):
        """Test for making sure api is called and response returned"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Prompt"))]
        )

        question = "When does the food bank open?"
        response = get_matching_question(question)

        mock_client.chat.completions.create.assert_called()
        self.assertEqual("Prompt", response)

    @patch("admin_panel.views.utilities.OpenAI")
    def test_get_matching_question_api_call_none(self, mock_openai):
        """Test for when api returns NONE"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="NONE"))]
        )

        question = "When does the food bank open?"
        response = get_matching_question(question)

        mock_client.chat.completions.create.assert_called()
        self.assertEqual(None, response)

    def test_get_corresponding_answer(self):
        """Test for correct answer returned"""
        question = "How can I schedule an appointment?"
        response = get_corresponding_answer(question)

        answer = "To schedule an appointment, visit calendly.com/sdfb."
        self.assertEqual(response, answer)

    @patch("admin_panel.views.utilities.forward_operator")
    def test_add_strike_forward_operator(self, mock_forward_operator):
        """Test strike system for forwarding to an operator when fails too many times"""
        log_mock = MagicMock()
        log_mock.add_strike.return_value = True

        strike_system_handler(log_mock)
        log_mock.add_strike.assert_called_once()
        mock_forward_operator.assert_called_once()

    def test_add_strike_no_forward_operator(self):
        """Test strike system management of strikes prior to operator forwarding"""
        log_mock = MagicMock()
        log_mock.add_strike.return_value = False

        strike_system_handler(log_mock)

        log_mock.add_strike.assert_called_once()

    def test_reset_strikes(self):
        """Test strike system reset"""
        log_mock = MagicMock()

        strike_system_handler(log_mock, reset=True)

        log_mock.reset_strikes.assert_called_once()
    
    def test_prompt_post_answer(self):
        """Test that the user is prompted with options after receiveg their answer"""
        request = self.factory.post("/prompt_post_answer/", {"From": "+17601231234"})
        response = prompt_post_answer(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("Would you like to return to the main menu, ask another question, or end the call?", response.content.decode())
        self.assertIn("process_post_answer", response.content.decode())

    def test_prompt_post_answer_spanisher(self):
        """Test that the user is prompted with options after receiveg their answer in spanish"""
        request = self.factory.post("/prompt_post_answer/", {"From": "+17603214321"})
        response = prompt_post_answer(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("Desea regresar al", response.content.decode())
        self.assertIn("process_post_answer", response.content.decode())
    
    def test_process_post_answer_no_input(self):
        """Test when no answer is given to the prompt."""
        request = self.factory.post("/process_post_answer/", {"From": "+17601231234"})
        response = process_post_answer(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("/prompt_post_answer/", response.content.decode())
    
    @patch("admin_panel.views.phone_service_faq.get_prompted_choice")
    def test_process_post_answer_question(self, mock_get_prompted_choice):
        """Test when user requests another question."""
        mock_get_prompted_choice.return_value = True

        request = self.factory.post("/process_post_answer/", {"SpeechResult": "Annother question.", "From": "+17603214321"})
        response = process_post_answer(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("/prompt_question/", response.content.decode())
    
    @patch("admin_panel.views.phone_service_faq.get_prompted_choice")
    def test_process_post_answer_hang_up(self, mock_get_prompted_choice):
        """Test when user requests to end the call."""
        mock_get_prompted_choice.return_value = False

        request = self.factory.post("/process_post_answer/", {"SpeechResult": "End call.", "From": "+17601231234"})
        response = process_post_answer(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Have a great day!", response.content.decode())
        self.assertIn("Hangup", response.content.decode())
    
    @patch("admin_panel.views.phone_service_faq.get_prompted_choice")
    def test_process_post_answer_hang_up_spanish(self, mock_get_prompted_choice):
        """Test when user requests to end the call."""
        mock_get_prompted_choice.return_value = False

        request = self.factory.post("/process_post_answer/", {"SpeechResult": "End call.", "From": "+17603214321"})
        response = process_post_answer(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("tengas un lindo", response.content.decode())
        self.assertIn("Hangup", response.content.decode())

    @patch("admin_panel.views.phone_service_faq.get_prompted_choice")
    def test_process_post_answer_menu(self, mock_get_prompted_choice):
        """Test when user requests to end the call."""
        mock_get_prompted_choice.return_value = None

        request = self.factory.post("/process_post_answer/", {"SpeechResult": "End call.", "From": "+17601231234"})
        response = process_post_answer(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("/answer/", response.content.decode())

    @patch("admin_panel.views.phone_service_faq.get_prompted_choice")
    @patch("admin_panel.views.phone_service_faq.translate_to_language")
    def test_process_post_answer_spanish(self, mock_translate_to_language, mock_get_prompted_choice):
        """Test for when the user speaks spanish and selects to ask another question"""
        mock_translate_to_language.return_vaue = "Translated to Spanish"
        mock_get_prompted_choice.return_value = True

        request = self.factory.post("/process_post_answer/", {"SpeechResult": "Annother question.", "From": "+17603214321"})
        response = process_post_answer(request)

        mock_translate_to_language.assert_called()
        self.assertEqual(response.status_code, 200)
        self.assertIn("/prompt_question/", response.content.decode())

class CallStatusUpdateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("call_status_update")  # Make sure this matches your urls.py
        self.phone_number = "+1234567890"
        self.log = Log.objects.create(
            phone_number=self.phone_number,
            time_started=timezone.now() - timedelta(seconds=30)
        )

    def test_call_status_update_success(self):
        time.sleep(1)
        response = self.client.post(self.url, {
            "CallStatus": "completed",
            "From": self.phone_number
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

        # Refresh the log from DB
        self.log.refresh_from_db()

        self.assertIsNotNone(self.log.time_ended)
        self.assertGreater(self.log.length_of_call.total_seconds(), 0)

    def test_call_status_update_ignores_non_completed(self):
        original_ended = self.log.time_ended
        response = self.client.post(self.url, {
            "CallStatus": "in-progress",
            "From": self.phone_number
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

        self.log.refresh_from_db()
        self.assertEqual(self.log.length_of_call.total_seconds(), 0)

    def test_call_status_update_missing_log(self):
        response = self.client.post(self.url, {
            "CallStatus": "completed",
            "From": "+19998887777"
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_call_status_update_invalid_method(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()["error"], "Method not allowed")
