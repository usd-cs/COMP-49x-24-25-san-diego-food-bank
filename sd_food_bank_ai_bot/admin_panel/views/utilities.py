from twilio.twiml.voice_response import VoiceResponse, Dial
from django.http import HttpResponse
from twilio.rest import Client
from django.conf import settings
from datetime import datetime

def strike_system_handler(log, reset = False):
    """Updates strikes within the log object associated with call as conversation progresses"""
    if log:
        if reset:
            log.reset_strikes()
        else:
            
            if log.add_strike():
                forward_operator()

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

def format_date_for_response(date_obj):
    """
    Format a date object to return a string representation of the day and date
    """
    date_format = date_obj.strftime("%A, %B %d")
    if 11 <= date_obj.day <= 13:
        suffix = "th"
    else:
        last = date_obj.day % 10
        if last == 1:
            suffix = "st"
        elif last == 2:
            suffix = "nd"
        elif last == 3:
            suffix = "rd"
        else:
            suffix = "th"

    date_final = date_format.replace(f"{date_obj.day}", f"{date_obj.day}{suffix}")

    return date_final