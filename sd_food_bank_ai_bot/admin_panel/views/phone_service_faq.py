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

TIMEOUT_LENGTH = 2 # The length of time the bot waits for a response

@csrf_exempt
def answer_call(request):
    """
    Brief greeting upon answering incoming phone calls.
    """
    caller_response = VoiceResponse()
    caller_response.say("Thank you for calling!")

    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/get_question_from_user/")
    gather.say("What can I help you with?")
    caller_response.append(gather)

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
    caller_response = VoiceResponse()
    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/get_question_from_user/")
    gather.say("What can I help you with?")
    caller_response.append(gather)
    
    return HttpResponse(str(caller_response), content_type='text/xml')

@csrf_exempt
def get_question_from_user(request):
    """
    Gets the users question and interprets it
    """
    speech_result = request.POST.get('SpeechResult', '')
    caller_response = VoiceResponse()
    if speech_result:
        question = get_matching_question(request, speech_result) # Log interpreted question?
        if question:
            question_encoded = urllib.parse.quote(question)
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/confirm_question/{question_encoded}/")
            gather.say(f"You asked: {question} Is this correct?")
            caller_response.append(gather)
        else: # No matching question found
            # Add a strike
            caller_response.say("Sorry, I don't have the answer to that at this time. Maybe try rephrasing your question.")
            caller_response.redirect("/prompt_question/")
    else:
        caller_response.say("Sorry, I couldn't understand that.") 
    
    return HttpResponse(str(caller_response), content_type='text/xml')

@csrf_exempt
def confirm_question(request, question):
    """
    Confirms the users question is correct and provides the answer
    """
    speech_result = request.POST.get('SpeechResult', '')
    caller_response = VoiceResponse()

    if speech_result:
        sentiment = get_response_sentiment(speech_result)
        if sentiment:
            question = urllib.parse.unquote(question)

            if "operator" in question:
                caller_response.say("I'm transferring you to an operator now. Please hold.")
                dial = Dial()
                dial.number("###-###-####")
                caller_response.append(dial)

                return HttpResponse(str(caller_response), content_type="text/xml")

            answer = get_corresponding_answer(request, question)
            
            caller_response.say(answer)

            caller_response.redirect("/prompt_question/")
        else: # If caller has indicated unsatisfactory response, add a string and retry
            # Add a strike
            caller_response.say("Sorry about that. Please try asking again or rephrasing.")
            caller_response.redirect("/prompt_question/")
    else:
        caller_response.say("Sorry, I couldn't understand that. Please try again.")
        caller_response.redirect("/prompt_question/")

    return HttpResponse(str(caller_response), content_type='text/xml')

@csrf_exempt
def get_response_sentiment(request, sentence):
    """
    Returns True if the given sentence is affirmative
    """
    # Query GPT for intent
    client = OpenAI()
    system_prompt = "Based on the following message, respond if it is AFFIRMATIVE or NEGATIVE."
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": sentence}
        ]
    )   
    response_pred = completion.choices[0].message.content

    if response_pred.upper() == "AFFIRMATIVE":
        return True
    return False

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

@csrf_exempt
def check_account(request):
    """
    Check the User table for phone number to check if the account exists. If it does, 
    relay the information such as the saved name to confirm the account.
    """
    # Have twilio send the caller's number using 'From'
    caller_number = request.POST.get('From', '')
    response = VoiceResponse()
    try: 
        # Query the User table for phone number and relay saved name.
        user = User.objects.get(phone_number=caller_number)
        response.say(f"Hello, {user.first_name} {user.last_name}.")

        # Confirm the account with the caller 
        gather = Gather(input="speech", timeout=2, action="/confirm_account/")
        gather.say("Is this your account? Please say yes or no.")
        response.append(gather)

        # Repeat the prompt if no input received
        response.redirect("/check_account/") 
    # Inform caller that there wasn't an account found
    except User.DoesNotExist:
        response.say("I'm sorry. We did not find an account associated with this phone number.")
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def confirm_account(request):
    """
    Process the caller's response. If they say yes, the account is confirmed, otherwise
    they will be prompted to try again.
    """
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    response = VoiceResponse()

    if "yes" in speech_result:
        response.say("Great! Your account has been confirmed!")
        response.redirect("/prompt_question/")
    else:
        response.say("I'm sorry, please try again.")
    
    return HttpResponse(str(response), content_type="text/xml")



