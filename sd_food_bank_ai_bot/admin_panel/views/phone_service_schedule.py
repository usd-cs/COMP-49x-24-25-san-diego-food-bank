from twilio.twiml.voice_response import VoiceResponse, Gather, Say

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

def get_user_phone_preference(request):
    pass

def get_current_phone_number(request):
    caller_number = request.POST.get('From', '')

    #regex check
    return None