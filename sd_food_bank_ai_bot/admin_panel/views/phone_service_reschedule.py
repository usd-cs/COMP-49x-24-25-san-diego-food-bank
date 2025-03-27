from .phone_service_schedule import *
from twilio.twiml.voice_response import VoiceResponse, Gather, Say

@csrf_exempt
def check_account_cancel_reschedule(request):
    """
    Check the User table for phone number to check if the account exists. If it does, 
    relay the information such as the saved name to confirm the account.

    In addition, this will return the user to the main menu if there is no appointment scheduled
    in their account (checks in the confirm_account_cancel_reschedule function)
    """
    # Have twilio send the caller's number using 'From'
    caller_number = get_phone_number(request)
    response = VoiceResponse()

    if caller_number:
        # Query the User table for phone number and relay saved name.
        user = User.objects.get(phone_number=caller_number)
        response.say(f"Hello, {user.first_name} {user.last_name}.")

        # Confirm the account with the caller 
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/confirm_account_cancel_reschedule/")
        gather.say("Is this your account? Please say yes or no.")
        response.append(gather)

        # Repeat the prompt if no input received
        response.redirect("/check_account_cancel_reschedule/")
    else:
        # Phone number is invalid
        response.say("Sorry, we are unable to help you at this time.")
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def confirm_account_cancel_reschedule(request):
    """
    Process the caller's response. If they say yes, the account is confirmed, otherwise
    they will be prompted to try again.

    In addition, this will return the user to the main menu if there is no appointment scheduled
    in their account.
    """
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    response = VoiceResponse()
    caller_number = get_phone_number(request)

    declaration = get_response_sentiment(request, speech_result)
    user = User.objects.get(phone_number=caller_number)
    appointments = AppointmentTable.objects.filter(user=user)
    
    if declaration:
        response.say("Great! Your account has been confirmed!")
        if appointments.exists():
            response.redirect("/prompt_reschedule_appointment/")
        else:
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/confirm_main_menu/")
            gather.say("We do not have an appointment registered with your number. Would you like to go back to the main menu?")
            response.append(gather)
    else:
        response.say("I'm sorry, please try again.")
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def confirm_main_menu(request):
    """
    Redirects user to main menu based on YES or NO
    """
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    declaration = get_response_sentiment(request, speech_result)
    response = VoiceResponse()

    if declaration:
        response.redirect("/answer/")
    else:
        response.hangup()

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def prompt_reschedule_appointment(request):
    """
    Asks the user what appointment they would like to reschedule
    """
    response = VoiceResponse()
    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/confirm_account_cancel_reschedule/")