from django.shortcuts import redirect
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ..models import FAQ, Log, User
import json
from django.http import HttpResponse
from twilio.twiml.voice_response import VoiceResponse, Gather, Say, Dial
from openai import OpenAI
import urllib.parse
import datetime
from .utilities import strike_system_handler, forward_operator, write_to_log, get_response_sentiment

BOT = "bot"
CALLER = "caller"
TIMEOUT_LENGTH = 3 # The length of time the bot waits for a response

@csrf_exempt
def answer_call(request):
    """
    Brief greeting upon answering incoming phone calls and prompt menu options.
    """
    phone_number = request.POST.get('From')
    log = Log.objects.create(phone_number = phone_number)
    caller_response = VoiceResponse()

    digit_input = request.POST.get('Digits', '')
    if digit_input:
        if digit_input == "1":
            caller_response.redirect("/check_account/?action=schedule")
        elif digit_input == "2": # Reschedule
            caller_response.redirect("/check_account/?action=reschedule")
        elif digit_input == "3": # Cancel
            caller_response.redirect("/check_account/?action=cancel")
        elif digit_input == "4": # FAQs 
            caller_response.redirect("/prompt_question/")
        elif digit_input == "0":
            forward_operator(log)
        else:
            caller_response.say("Sorry, that feature has not been added yet")
        

    gather = Gather(num_digits=1)
    gather.say("Thank you for calling the San Diego Food Bank! Press 1 to\
         schedule an appointment, press 2 to reschedule an appointment,\
             press 3 to cancel an appointment, press 4 to ask about specific\
                inquiries, or press 0 to be forwarded to an operator.")
    
    write_to_log(log, BOT, "Thank you for calling the San Diego Food Bank! Press 1 to\
         schedule an appointment, press 2 to reschedule an appointment,\
             press 3 to cancel an appointment, press 4 to ask about specific\
                inquiries, or press 0 to be forwarded to an operator.")
    caller_response.append(gather)
    # If no input, repeat process
    caller_response.redirect("/answer/")

    return HttpResponse(str(caller_response), content_type='text/xml')

@csrf_exempt
def call_status_update(request):
    """
    Looks at call status from twilio webhook and stores call status data when receiving a POST request.
    """
    if request.method == 'POST':
        call_status = request.POST.get('CallStatus')
        phone_number = request.POST.get('From')
    
        if call_status == 'completed':
            log = Log.objects.filter(phone_number=phone_number).last()
            if log:
                log.time_ended = datetime.now()
                
                if log.time_started:
                    call_duration = log.time_ended - log.time_started
                    log.length_of_call = call_duration

                log.save()

        return JsonResponse({"status": "success"})

    else:
        return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def prompt_question(request):
    """
    Used to prompt the user for a question. Main use is to loop till end of call.
    """
    phone_number = request.POST.get('From')
    log = Log.objects.filter(phone_number=phone_number).last()
    caller_response = VoiceResponse()
    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/get_question_from_user/")
    gather.say("What can I help you with?")
    write_to_log(log, BOT, "What can I help you with?")
    caller_response.append(gather)
    
    return HttpResponse(str(caller_response), content_type='text/xml')

@csrf_exempt
def get_question_from_user(request):
    """
    Gets the users question and interprets it
    """
    speech_result = request.POST.get('SpeechResult', '')
    phone_number = request.POST.get('From')
    log = Log.objects.filter(phone_number=phone_number).last()
    write_to_log(log, CALLER, speech_result)
    caller_response = VoiceResponse()
    if speech_result:
        question = get_matching_question(request, speech_result)
        if question:
            question_encoded = urllib.parse.quote(question)
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/confirm_question/{question_encoded}/")
            gather.say(f"You asked: {question} Is this correct?")
            write_to_log(log, BOT, f"You asked: {question} Is this correct?")
            caller_response.append(gather)
        else: # No matching question found
            # Add a strike
            strike_system_handler(log)
            caller_response.say("Sorry, I don't have the answer to that at this time. Maybe try rephrasing your question.")
            write_to_log(log, BOT, "Sorry, I don't have the answer to that at this time. Maybe try rephrasing your question.")
            caller_response.redirect("/prompt_question/")
    else:
        caller_response.say("Sorry, I couldn't understand that.")
        write_to_log(log, BOT, "Sorry, I couldn't understand that.")
    
    return HttpResponse(str(caller_response), content_type='text/xml')

@csrf_exempt
def confirm_question(request, question):
    """
    Confirms the users question is correct and provides the answer
    """
    speech_result = request.POST.get('SpeechResult', '')
    phone_number = request.POST.get('From')
    log = Log.objects.filter(phone_number=phone_number).last()
    caller_response = VoiceResponse()
    write_to_log(log, CALLER, speech_result)

    if speech_result:
        sentiment = get_response_sentiment(request, speech_result)
        if sentiment:
            question = urllib.parse.unquote(question)

            if "operator" in question:
                return forward_operator(log)

            answer = get_corresponding_answer(request, question)
            
            caller_response.say(answer)
            write_to_log(log, BOT, answer)

            caller_response.redirect("/prompt_question/")
        else: # If caller has indicated unsatisfactory response, add a string and retry
            # Add a strike
            strike_system_handler(log)
            caller_response.say("Sorry about that. Please try asking again or rephrasing.")
            write_to_log(log, BOT, "Sorry about that. Please try asking again or rephrasing.")
            caller_response.redirect("/prompt_question/")
    else:
        caller_response.say("Sorry, I couldn't understand that. Please try again.")
        write_to_log(log, BOT, "Sorry, I couldn't understand that. Please try again.")
        caller_response.redirect("/prompt_question/")

    return HttpResponse(str(caller_response), content_type='text/xml')

@csrf_exempt
def get_matching_question(request, question):
    """
    Takes in a users question and finds the most closely related question, returning that question.
    If there are no related questions, none is returned.
    """ 
    client = OpenAI()

    # Gather all questions to be used in prompt
    questions = FAQ.objects.values_list('question', flat=True)
    questions = [question for question in questions]
    questions.append("Can I speak to an operator?")

    # Set the system prompt to provide instructions on what to do
    system_prompt = f"You are a food pantry assistant with one job. When a user sends you a question, you find the closest match from questions you have memorized and respond with that question. If the question the user asks does not match any of your stored questions, respond with NONE. Only respond with the matching question or NONE.\nYour memorized questions are:{questions}"

    # Make an API call to find the question
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
    )

    # Extract the question from the response
    question_pred = completion.choices[0].message.content
    if question_pred == "NONE":
        return None

    return question_pred

@csrf_exempt
def get_corresponding_answer(request, question):
    """
    Takes in a predefined question and returns the matching answer.
    If there is no question/answer match in the database, None is returned.
    """
    answer = FAQ.objects.filter(question__iexact=question).first().answer
    return answer