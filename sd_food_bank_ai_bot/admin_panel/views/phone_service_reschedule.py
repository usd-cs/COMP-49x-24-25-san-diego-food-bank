from .phone_service_schedule import *
from .utilities import get_phone_number
from twilio.twiml.voice_response import VoiceResponse, Gather, Say

@csrf_exempt
def prompt_reschedule_appointment_over_one(request):
    """
    Asks the user what appointment they would like to reschedule if they have over one appointment
    """
    caller_number = get_phone_number(request)
    user = User.objects.get(phone_number=caller_number)
    appointments = AppointmentTable.objects.filter(user=user)

    response = VoiceResponse()
    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/generate_requested_date/")
    gather.say("Which appointment would you like to reschedule?")
    response.append(gather)

    requested_date = generate_requested_date(request)

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def generate_requested_date(request):
    """
    Uses GPT to generate a most-likely date that the caller asked for.
    """
    speech_result = request.POST.get('SpeechResult', '')
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

        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/confirm_requested_date/{date_encoded}/")
        gather.say(f"Your requested day was {response_pred}. Is that correct?")
        response.append(gather)
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
    user = User.objects.get(phone_number=caller_number)
    speech_result = request.POST.get('SpeechResult', '')
    response = VoiceResponse()
    declaration = get_response_sentiment(request, speech_result)

    try:
        requested_date_str = urllib.parse.unquote(date_encoded)
        requested_date = datetime.strptime(requested_date_str, "%Y-%m-%d").date() # From str to date
    except (ValueError, TypeError):
        response.say("Sorry, we could not understand the date. Let's try again.")
        response.redirect("/prompt_reschedule_appointment_over_one/")
        return HttpResponse(str(response), content_type="text/xml")
    
    if declaration:
        appointment_exists = AppointmentTable.objects.filter(user=user, date__date=requested_date).exists()
        if appointment_exists:
            date_encoded_url = urllib.parse.quote(date_encoded)
            response.redirect(f"/reschedule_appointment/{date_encoded_url}/") # Send to rescheduling
        else:
            response.say("Sorry, this is not in your appointments.")
            response.redirect("/prompt_reschedule_appointment_over_one")
            return HttpResponse(str(response), content_type="text/xml")
    else:
        response.redirect("/prompt_reschedule_appointment_over_one/")
    
    return HttpResponse(str(response), content_type="text/xml")