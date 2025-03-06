from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from .phone_service_faq import get_response_sentiment
from django.views.decorators.csrf import csrf_exempt
from ..models import User
from django.http import HttpResponse
from openai import OpenAI
import re


TIMEOUT_LENGTH = 2 # The length of time the bot waits for a response

@csrf_exempt
def get_phone_number(request):
    """
    Gets the user phone number from the post header
    """
    caller_number = request.POST.get('From', '')

    #regex check
    expression = "^\+[1-9]\d{1,14}$" # E.164 compliant phone numbers
    valid = re.match(expression, caller_number)
    
    if valid:
        return caller_number
    return None

@csrf_exempt
def check_account(request):
    """
    Check the User table for phone number to check if the account exists. If it does, 
    relay the information such as the saved name to confirm the account.
    """
    # Have twilio send the caller's number using 'From'
    caller_number = get_phone_number(request)
    response = VoiceResponse()
    try: 
        # Query the User table for phone number and relay saved name.
        user = User.objects.get(phone_number=caller_number)
        response.say(f"Hello, {user.first_name} {user.last_name}.")

        # Confirm the account with the caller 
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/confirm_account/")
        gather.say("Is this your account? Please say yes or no.")
        response.append(gather)

        # Repeat the prompt if no input received
        response.redirect("/check_account/") 
    # Inform caller that there wasn't an account found
    except User.DoesNotExist:
        response.say("I'm sorry. We did not find an account associated with this phone number.") # Later change prompt and send to account registration
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def confirm_account(request):
    """
    Process the caller's response. If they say yes, the account is confirmed, otherwise
    they will be prompted to try again.
    """
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    response = VoiceResponse()

    declaration = get_response_sentiment(request, speech_result)

    if declaration:
        response.say("Great! Your account has been confirmed!")
        response.redirect("/prompt_question/")
    else:
        response.say("I'm sorry, please try again.")
    
    return HttpResponse(str(response), content_type="text/xml")

def get_nearest_available_slot(requested_time):
    """
    Simulate calendar scheduling for the nearest available appointment.
    Later we can just replace this with whatever API calls that are necessary to 
    Acuity.

    If request time is "3:00 pm", we will return "3:15 pm" as nearest available.
    """
    return "3:15 PM"

@csrf_exempt
def schedule_nearest_available(request):
    """
    Provides the nearest available appointment time to the caller.
    The caller is then prompted to confirm the appointment.
    """
    requested_time = "3:00 PM" # Simulated for now 
    available_slot = get_nearest_available_slot(requested_time)

    response = VoiceResponse()
    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/handle_schedule_response/")
    gather.say(f"The nearest available appointment is at {available_slot}. Would you like to schedule this appointment?")
    response.append(gather)

    response.redirect("/schedule_nearest_available/") # Reprompt if no response

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def handle_schedule_response(request):
    """
    Process the caller's response to the proposed appointment time.
    If they say yes, confirm the appointment, otherwise ask if they want other times.
    """
    speech_result = request.POST.get("SpeechResult", " ").strip().lower()
    response = VoiceResponse()

    if "yes" in speech_result:
        response.say("Your appointment has been scheduled! Thank you.")
        response.hangup()
    else: 
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/handle_schedule_options/")
        gather.say("Would you like to hear other available times or a different date? Please say 'other times' or 'different date'.")
        response.append(gather)
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def handle_schedule_options(request):
    """
    Process the caller's follow up choice. 
    If they say 'Other times', provide an alternative available slot.
    If they say 'Different date', handle it accordingly.
    """
    speech_result = request.POST.get("SpeechResult", "").strip().lower()
    response = VoiceResponse()

    if "other times" in speech_result:
        # Another simulated available slot 
        alternative_slot = "3:45 PM"
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/handle_schedule_response/")
        gather.say(f"Another available appointment is available at {alternative_slot}. Would you like to schedule this appointment? Please say yes or no.")
        response.append(gather)
        response.redirect("/schedule_nearest_available/")
    elif "different date" in speech_result:
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/handle_date_input/")
        gather.say("What date would you like to schedule an appointment for?")
        response.append(gather)
    else:
        response.say("I'm sorry, I didn't understand that.")
        response.redirect("/schedule_nearest_available/")
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def handle_date_input(request):
    """
    Processes the caller's date input, queries for available slots on that day,
    and offers the nearest appointment.
    """
    date_input = request.POST.get("SpeechResult", "").strip()
    response = VoiceResponse()
    
    # Simulate an available slot for the specified date.
    available_slot = "4:00 PM"
    
    # Prompt the caller with the available slot and ask for confirmation.
    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/handle_schedule_response/")
    gather.say(f"For {date_input}, the nearest available appointment is at {available_slot}. Would you like to schedule this appointment? Please say yes or no.")
    response.append(gather)
    
    return HttpResponse(str(response), content_type="text/xml")
