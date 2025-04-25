from ..models import User, AppointmentTable, Log
from .utilities import write_to_log
from django.views.decorators.csrf import csrf_exempt
from .utilities import get_phone_number, get_response_sentiment, translate_to_language
from twilio.twiml.voice_response import VoiceResponse, Gather
from django.http import HttpResponse
from openai import OpenAI
import urllib.parse
from datetime import datetime
from .phone_service_schedule import CALLER, BOT

TIMEOUT_LENGTH = 4


@csrf_exempt
def prompt_reschedule_appointment_over_one(request):
    """
    Asks the user what appointment they would like to reschedule if they
    have over one appointment
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    user = User.objects.get(phone_number=caller_number)

    response = VoiceResponse()
    
    if user.language == "en":
        gather = Gather(input="speech",
                    timeout=TIMEOUT_LENGTH, action="/generate_requested_date/")
        gather.say("Which appointment would you like to reschedule?")
        write_to_log(log, BOT, "Which appointment would you like to reschedule?")
    else:
        gather = Gather(input="speech",
                    timeout=TIMEOUT_LENGTH, action="/generate_requested_date/", language = 'es-MX')
        gather.say("Que cita le gustaria reprogramar?", language = 'es-MX')
        write_to_log(log, BOT, "Que cita le gustaria reprogramar?")
    response.append(gather)
    response.redirect("/prompt_reschedule_appointment_over_one/")

    generate_requested_date(request)

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def generate_requested_date(request):
    """
    Uses GPT to generate a most-likely date that the caller asked for.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    user = User.objects.get(phone_number=caller_number)
    speech_result = request.POST.get('SpeechResult', '')
    write_to_log(log, CALLER, speech_result)
    if user.language == "es":
        speech_result = translate_to_language("es", "en", speech_result)
    response = VoiceResponse()

    if speech_result:
        # Query GPT to extract the date
        client = OpenAI()
        system_prompt = (
            "Please extract the most likely intended appointment date from this message."
            "Respond with a date in the format YYYY-MM-DD. If no date is present, return NONE."
        )
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": speech_result}
            ]
        )
        response_pred = completion.choices[0].message.content.strip()
        date_encoded = urllib.parse.quote(response_pred)

        if user.language == "en":
            gather = Gather(input="speech",
                        timeout=TIMEOUT_LENGTH,
                        action=f"/confirm_requested_date/{date_encoded}/")
            gather.say(f"Your requested day was {response_pred}. Is that correct?")
            write_to_log(log, BOT, f"Your requested day was {response_pred}. Is that correct?")
        else:
            gather = Gather(input="speech",
                        timeout=TIMEOUT_LENGTH,
                        action=f"/confirm_requested_date/{date_encoded}/", language = 'es-MX')
            out_speech_es = translate_to_language("en", "es", f"Your requested day was {response_pred}. Is that correct?")
            gather.say(out_speech_es, language = 'es-MX')
            write_to_log(log, BOT, out_speech_es)
        response.append(gather)
        response.redirect("/prompt_reschedule_appointment_over_one/")
    else:
        response.redirect("/prompt_reschedule_appointment_over_one/")

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def confirm_requested_date(request, date_encoded):
    """
    Asks the user if the date they requested is correct YES or NO and checks
    that the appointment is in their appointment list
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    user = User.objects.get(phone_number=caller_number)
    speech_result = request.POST.get('SpeechResult', '')
    write_to_log(log, CALLER, speech_result)
    if user.language == "es":
        speech_result = translate_to_language("es", "en", speech_result)
    response = VoiceResponse()
    declaration = get_response_sentiment(speech_result)

    try:
        requested_date_str = urllib.parse.unquote(date_encoded)
        requested_date = datetime.strptime(requested_date_str, "%Y-%m-%d").date()  # From str to date
    except (ValueError, TypeError):
        if user.language == "en":
            response.say("Sorry, we could not understand the date. Let's try again.")
            write_to_log(log, BOT, "Sorry, we could not understand the date. Let's try again.")
        else:
            response.say("Lo sentimos, no pudimos entender la fecha. Intentalo de nuevo.", language = 'es-MX')
            write_to_log(log, BOT, "Lo sentimos, no pudimos entender la fecha. Intentalo de nuevo.")
        response.redirect("/prompt_reschedule_appointment_over_one/")
        return HttpResponse(str(response), content_type="text/xml")

    if declaration:
        appointment_exists = AppointmentTable.objects.filter(user=user, date__date=requested_date).exists()
        if appointment_exists:
            date_encoded_url = urllib.parse.quote(date_encoded)
            # Send to rescheduling
            response.redirect(f"/reschedule_appointment/{date_encoded_url}/")

        else:
            if user.language == "en":
                response.say("Sorry, this is not in your appointments.")
                write_to_log(log, BOT, "Sorry, this is not in your appointments.")
            else:
                response.say("Lo sentimos, esto no esta en tus citas.", language = 'es-MX')
                write_to_log(log, BOT, "Lo sentimos, esto no esta en tus citas.")
            response.redirect("/prompt_reschedule_appointment_over_one")
            return HttpResponse(str(response), content_type="text/xml")
    else:
        response.redirect("/prompt_reschedule_appointment_over_one/")

    return HttpResponse(str(response), content_type="text/xml")
