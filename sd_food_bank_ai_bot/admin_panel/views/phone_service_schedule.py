from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from .phone_service_faq import get_response_sentiment
import re

TIMEOUT_LENGTH = 2 # The length of time the bot waits for a response

def get_phone_number(request):
    """
    Prompts the user by asking if the current phone number should be used or not.
    """
    caller_response = VoiceResponse()

    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/get_user_phone_preference/")
    gather.say("Would you like to use the number you're calling from, or provide a different one?")
    caller_response.append(gather)

    return HttpResponse(str(caller_response), content_type='text/xml')

def get_user_phone_preference(request, sentence):
    """
    Gets whether the user wants to use the current number or a different number.
    """
    # Query GPT for intent
    client = OpenAI()
    system_prompt = "Based on the following message, respond whether the user is asking to use their CURRENT phone number or OTHER. Respond only with CURRENT or OTHER."
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": sentence}
        ]
    )   
    response_pred = completion.choices[0].message.content

def get_current_phone_number(request):
    """
    Gets the phone number that the user is calling from.
    """
    caller_number = request.POST.get('From', '')

    #regex check
    expression = "^\+[0-9]{11}$" # include + for country code
    valid = re.match(expression, caller_number)

    if valid:
        return expression
    return None