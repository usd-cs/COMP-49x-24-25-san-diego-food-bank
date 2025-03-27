from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from .phone_service_faq import get_response_sentiment
from .phone_service_schedule import get_phone_number
from django.views.decorators.csrf import csrf_exempt
from ..models import User, AppointmentTable
from django.http import HttpResponse
from openai import OpenAI
from datetime import time, datetime, timedelta
import urllib.parse
# Not sure how many of these ^ we will actually need 

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
        response.redirect("/INSERT_URL_TO_REROUTE_NO_APPOINTEMNT/")
    elif num_appointments == 1:
        appointment = AppointmentTable.objects.get(user=user)
        appointment_id = appointment.id

        response.redirect(f"/INSERT_URL_TO_CONFIRM_APPOINTMENT_CANCELLATION/{appointment_id}/")
    else:
        response.redirect("/INSERT_URL_TO_ASKING_FOR_APPOINTMENT/")

    return HttpResponse(str(response), content_type="text/xml")