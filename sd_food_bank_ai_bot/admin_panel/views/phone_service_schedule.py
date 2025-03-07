from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from .phone_service_faq import get_response_sentiment
from django.views.decorators.csrf import csrf_exempt
from ..models import User
from django.http import HttpResponse
from openai import OpenAI
import urllib.parse
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
        if caller_number:
            # Query the User table for phone number and relay saved name.
            user = User.objects.get(phone_number=caller_number)
            response.say(f"Hello, {user.first_name} {user.last_name}.")

            # Confirm the account with the caller 
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/confirm_account/")
            gather.say("Is this your account? Please say yes or no.")
            response.append(gather)

            # Repeat the prompt if no input received
            response.redirect("/check_account/")
        else:
            # Phone number is invalid
            response.say("Sorry, we are unable to help you at this time.")
    # Inform caller that there wasn't an account found
    except User.DoesNotExist:
        # User does not exist to being registration process
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/get_name/")
        gather.say("Can I get your first and last name please?")
        response.append(gather)
    
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
        response.redirect("/prompt_question/") # Replace with get_date later
    else:
        response.say("I'm sorry, please try again.")
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def get_name(request):
    """
    Processes the users response to extract their name
    """
    speech_result = request.POST.get('SpeechResult', '')
    response = VoiceResponse()
    
    if speech_result:
        # Query GPT for name (incase other words are said)
        client = OpenAI()
        system_prompt = "Please extract someones first and last name from the following message. Only respond with the first and last name."
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": speech_result}
            ]
        )   
        response_pred = completion.choices[0].message.content

        name_encoded = urllib.parse.quote(response_pred)
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/process_name_confirmation/{name_encoded}/")
        gather.say(f"Your name is {response_pred}. Is that correct?")
        response.append(gather)
    else:
        response.redirect("/check_account/")

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def process_name_confirmation(request, name_encoded):
    """
    Based on confirmation of name, routes the flow of the conversation.
    """
    speech_result = request.POST.get('SpeechResult', '')
    confirmation = get_response_sentiment(request, speech_result)
    
    response = VoiceResponse()
    if confirmation:
        # Unencode the name and split into first and last name
        name = urllib.parse.unquote(name_encoded)
        name = name.split()

        first_name = name[0]
        last_name = None
        if len(name) >= 2:
            last_name = name[-1]
        else:
            last_name = ""

        caller_number = get_phone_number(request)

        # Create user account
        new_user = User.objects.create(
                first_name=first_name,
                last_name=last_name,
                phone_number=caller_number,
        )

        # Send to get_date function
        response.say("Rerouting to get date.") # Place holder
    else:
        # Add a strike
        response.say("I'm sorry, please try again.")
        response.redirect("/check_account/")
    
    return HttpResponse(str(response), content_type="text/xml")