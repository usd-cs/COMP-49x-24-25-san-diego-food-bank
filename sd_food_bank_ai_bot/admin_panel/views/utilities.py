from twilio.twiml.voice_response import VoiceResponse, Dial
from django.http import HttpResponse

def strike_system_handler(log, reset = False):
    if reset:
        log.reset_strikes()
    else:
        if log.add_strike():
            forward_operator()

def forward_operator():
    caller_response = VoiceResponse()

    caller_response.say("I'm transferring you to an operator now. Please hold.")
    dial = Dial()
    dial.number("###-###-####")
    caller_response.append(dial)

    return HttpResponse(str(caller_response), content_type="text/xml")