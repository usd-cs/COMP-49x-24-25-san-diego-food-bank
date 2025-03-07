from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from .phone_service_faq import get_response_sentiment
from django.views.decorators.csrf import csrf_exempt
from ..models import User
from django.http import HttpResponse
from openai import OpenAI
import re


TIMEOUT_LENGTH = 3 # The length of time the bot waits for a response

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