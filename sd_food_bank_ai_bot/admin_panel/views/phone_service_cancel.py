from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from .phone_service_faq import get_response_sentiment
from .phone_service_schedule import get_phone_number
from django.views.decorators.csrf import csrf_exempt
from ..models import User, AppointmentTable
from django.http import HttpResponse
from openai import OpenAI
from datetime import time, datetime, timedelta
from .utilities import format_date_for_response
import urllib.parse
# Not sure how many of these ^ we will actually need 

TIMEOUT_LENGTH = 2 # The length of time the bot waits for a response

@csrf_exempt
def cancel_initial_routing(request):
    """
    Decide which route the user should follow when calling to cancel an appointment
    based on the number of appointments they have scheduled.
    """
    caller_number = get_phone_number(request)
    response = VoiceResponse()

    user = User.objects.get(phone_number=caller_number) 
    num_appointments = AppointmentTable.objects.filter(user=user).count()

    if num_appointments == 0:
        response.redirect("/reroute_no_appointment/")
    elif num_appointments == 1:
        appointment = AppointmentTable.objects.get(user=user)
        appointment_id = appointment.id

        response.redirect(f"/prompt_cancellation_confirmation/{appointment_id}/")
    else:
        response.redirect("/INSERT_URL_TO_ASKING_FOR_APPOINTMENT/") #TODO route this to appointment selection

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def prompt_cancellation_confirmation(request, appointment_id):
    """
    Prompts the user to ensure they wish to cancel their appointment
    """
    response = VoiceResponse()
    appointment = AppointmentTable.objects.get(pk=appointment_id)

    start_time = appointment.start_time
    date = appointment.date

    time_str = start_time.strftime('%I:%M %p')
    date_str = format_date_for_response(date)

    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/cancellation_confirmation/{appointment_id}/")
    gather.say(f"Are you sure you want to cancel your appointment on {date_str} at {time_str}?")
    response.append(gather)
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def cancellation_confirmation(request, appointment_id):
    """
    Get the users response and proceed with the cancellation accordingly
    """
    response = VoiceResponse()
    speech_result = request.POST.get('SpeechResult', '')
    if speech_result:
        declaration = get_response_sentiment(request, speech_result)
        if declaration:
            response.redirect(f"/cancel_appointment/{appointment_id}/")
        else:
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/return_main_menu_response/")
            gather.say("Would you like to go back to the main menu?")
            response.append(gather)
    else:
        response.redirect(f"/prompt_cancellation_confirmation/{appointment_id}/")

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def return_main_menu_response(request):
    """
    Route the user back to the main menu or hang up, depending on their response.
    """
    response = VoiceResponse()
    speech_result = request.POST.get('SpeechResult', '')

    if speech_result:
        declaration = get_response_sentiment(request, speech_result)
        if declaration:
            response.redirect("/answer/")
        else:
            response.say("Have a great day!")
            response.hangup()
    else:
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/return_main_menu_response/")
        gather.say("Would you like to go back to the main menu?")
        response.append(gather)

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def reroute_no_appointment(request):
    """
    Prompt user for if they would like to go back to the main menu when they do not have an appointment.
    """
    response = VoiceResponse()

    response.say("We do not have an appointment registered with your number.")
    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/return_main_menu_response/")
    gather.say("Would you like to go back to the main menu?")
    response.append(gather)
    
    return HttpResponse(str(response), content_type="text/xml")
