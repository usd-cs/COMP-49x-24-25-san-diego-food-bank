from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from .phone_service_faq import get_response_sentiment
from django.http import HttpResponse
from openai import OpenAI
import re


TIMEOUT_LENGTH = 2 # The length of time the bot waits for a response

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