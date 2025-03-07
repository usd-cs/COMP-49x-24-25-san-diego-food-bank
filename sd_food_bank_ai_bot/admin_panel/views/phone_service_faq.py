from django.shortcuts import redirect
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ..models import FAQ, Log
import json
from django.http import HttpResponse
from twilio.twiml.voice_response import VoiceResponse, Gather, Say, Dial
from openai import OpenAI
import urllib.parse
import datetime
from .utilities import strike_system_handler, forward_operator

BOT = "bot"
CALLER = "caller"

@csrf_exempt
def answer_call(request):
    """
    Brief greeting upon answering incoming phone calls.
    """
    phone_number = request.POST.get('From')
    log = Log.objects.create(phone_number = phone_number)
    caller_response = VoiceResponse()
    caller_response.say("Thank you for calling!")
    log.add_transcript(speaker = BOT, message = "Thank you for calling!")

    gather = Gather(input="speech", timeout=5, action="/get_question_from_user/")
    gather.say("What can I help you with?")
    log.add_transcript(speaker = BOT, message = "What can I help you with?")
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
    phone_number = request.POST.get('From')
    log = Log.objects.filter(phone_number=phone_number).last()
    caller_response = VoiceResponse()
    gather = Gather(input="speech", timeout=5, action="/get_question_from_user/")
    gather.say("What can I help you with?")
    log.add_transcript(speaker = BOT, message = "What can I help you with?")
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
    log.add_transcript(speaker = CALLER, message = speech_result)
    caller_response = VoiceResponse()
    if speech_result:
        question = get_matching_question(request, speech_result)
        if question:
            question_encoded = urllib.parse.quote(question)
            gather = Gather(input="speech", timeout=5, action=f"/confirm_question/{question_encoded}/")
            gather.say(f"You asked: {question} Is this correct?")
            log.add_transcript(speaker = BOT, message = f"You asked: {question} Is this correct?")
            caller_response.append(gather)
        else: # No matching question found
            # Add a strike
            strike_system_handler(log)
            caller_response.say("Sorry, I don't have the answer to that at this time. Maybe try rephrasing your question.")
            log.add_transcript(speaker = BOT, message = "Sorry, I don't have the answer to that at this time. Maybe try rephrasing your question.")
            caller_response.redirect("/prompt_question/")
    else:
        caller_response.say("Sorry, I couldn't understand that.")
        log.add_transcript(speaker = BOT, message = "Sorry, I couldn't understand that.")
    
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
    log.add_transcript(speaker = CALLER, message = speech_result)

    if speech_result:
        # Query GPT for intent
        client = OpenAI()
        system_prompt = "Based on the following message, respond if it is AFFIRMATIVE or NEGATIVE."
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": speech_result}
            ]
        )   
        response_pred = completion.choices[0].message.content
        if response_pred.upper() == "AFFIRMATIVE":
            question = urllib.parse.unquote(question)

            if "operator" in question:
                return forward_operator(log)

            answer = get_corresponding_answer(request, question)
            
            caller_response.say(answer)
            log.add_transcript(speaker = BOT, message = answer)

            caller_response.redirect("/prompt_question/")
        else: # If caller has indicated unsatisfactory response, add a string and retry
            # Add a strike
            strike_system_handler(log)
            caller_response.say("Sorry about that. Please try asking again or rephrasing.")
            log.add_transcript(speaker = BOT, message = "Sorry about that. Please try asking again or rephrasing.")
            caller_response.redirect("/prompt_question/")
    else:
        caller_response.say("Sorry, I couldn't understand that. Please try again.")
        log.add_transcript(speaker = BOT, message = "Sorry, I couldn't understand that. Please try again.")
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