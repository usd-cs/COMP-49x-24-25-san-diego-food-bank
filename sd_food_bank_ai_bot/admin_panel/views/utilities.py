from twilio.twiml.voice_response import VoiceResponse, Dial
from .phone_service_schedule import get_response_sentiment, get_phone_number
from ..models import User, AppointmentTable
from django.http import HttpResponse
from twilio.rest import Client
from django.conf import settings

def strike_system_handler(log, reset = False):
    """Updates strikes within the log object associated with call as conversation progresses"""
    if log:
        if reset:
            log.reset_strikes()
        else:
            
            if log.add_strike():
                forward_operator()

def return_main_menu(request):
    """
    Redirects user to main menu based on YES or NO sentiment
    """
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    declaration = get_response_sentiment(request, speech_result)
    response = VoiceResponse()

    if declaration:
        response.redirect("/answer/")
    else:
        response.hangup()

    return HttpResponse(str(response), content_type="text/xml")

def appointment_count(request):
    """
    Returns the appointment count of user
    """
    caller_number = get_phone_number(request)
    user = User.objects.get(phone_number=caller_number)
    appointment_count = AppointmentTable.objects.filter(user=user).count()

    return appointment_count

def forward_operator(log):
    """Relays info to and forwards caller to operator because requested or failed strike system"""
    caller_response = VoiceResponse()

    caller_response.say("I'm transferring you to an operator now. Please hold.")
    write_to_log(log, "bot", "I'm transferring you to an operator now. Please hold.")
    dial = Dial()
    dial.number("###-###-####")
    caller_response.append(dial)

    return HttpResponse(str(caller_response), content_type="text/xml")

def write_to_log(log, speaker, message):
    """Log conversation as conversation progresses attributing each dialogue to a specific party"""
    if log:
        log.add_transcript(speaker = speaker, message = message)

def send_sms(phone_number_to, message_to_send):
    """Send confirmation details via sms to caller"""
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    try:
        message = client.messages.create(
            body=message_to_send,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number_to)
        return message
    except Exception as e:
        return None
