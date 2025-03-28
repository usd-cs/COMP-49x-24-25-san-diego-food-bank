from .phone_service_schedule import CALLER, BOT
from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from .phone_service_faq import get_response_sentiment
from .phone_service_schedule import get_phone_number
from django.views.decorators.csrf import csrf_exempt
from ..models import User, AppointmentTable, Log
from django.http import HttpResponse
from openai import OpenAI
from datetime import time, datetime, timedelta
from .utilities import format_date_for_response, write_to_log
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
        response.redirect("/ask_appointment_to_cancel/")

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def ask_appointment_to_cancel(request):
    """
    Ask the user which appointment they want to cancel when multiple are scheduled
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    response = VoiceResponse()
    user = User.objects.get(phone_number=caller_number)
    appointments = AppointmentTable.objects.filter(user = user)

    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/process_appointment_selection/")

    appointments_formatted = []
    for appointment in appointments:
        time_str = appointment.start_time.strftime('%I:%M %p')
        date_str = format_date_for_response(appointment.date)
        appointments_formatted.append(f"{date_str} at {time_str}")

    gather.say("Which appointment would you like to cancel? " + ", ".join(appointments_formatted))
    write_to_log(log, BOT, "Which appointment would you like to cancel? " + ", ".join(appointments_formatted))

    response.append(gather)

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def process_appointment_selection(request):
    """
    Process the user's response about which appointment to cancel
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    response = VoiceResponse()
    user = User.objects.get(phone_number=caller_number)
    appointments = AppointmentTable.objects.filter(user = user)

    speech_result = request.POST.get('SpeechResult', '')
    write_to_log(log, CALLER, speech_result)

    appointments_formatted = []
    for appointment in appointments:
        time_str = appointment.start_time.strftime('%I:%M %p')
        date_str = format_date_for_response(appointment.date)
        appointments_formatted.append(f"{date_str} at {time_str}")

    appointment_options = "\n".join(appt for appt in appointments_formatted)

    if speech_result:
        # Query GPT for which appointment best aligns with the user's choice
        client = OpenAI()
        system_prompt = (f"The user said: '{speech_result}'.\n"
                         f"Here are the available appointments:\n{appointment_options}\n"
                         "Based on what the user said, which appointment do they want to cancel."
                         "Respond with a single number, 0 for the first appointment, 1 for the second appointment, and so on."
                         "If you are unsure, respond only with UNCERTAIN."
                         "If none of the appointments match the date they said, respond only with NONE.")
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": system_prompt}
            ]
        )   
        response_pred = completion.choices[0].message.content.strip()

        if response_pred.upper() == "UNCERTAIN":
            response.say("I didn't catch that. Please try again.")
            write_to_log(log, BOT, "I didn't catch that. Please try again.")
            response.redirect("/ask_appointment_to_cancel/")
        elif response_pred.upper() == "NONE":
            response.say("Sorry, we don't have you scheduled for that. Please try again.")
            write_to_log(log, BOT, "Sorry, we don't have you scheduled for that. Please try again.")
            response.redirect("/ask_appointment_to_cancel/")
        else:
            try:
                index = int(response_pred)
                if 0 <= index < len(appointments):
                    appointment_id = appointments[index].id

                    response.redirect(f"/prompt_cancellation_confirmation/{appointment_id}/")
                else:
                    raise ValueError
            except ValueError:
                response.say("I didn't catch that. Please try again.")
                write_to_log(log, BOT, "I didn't catch that. Please try again.")
                response.redirect("/ask_appointment_to_cancel/")
        
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def prompt_cancellation_confirmation(request, appointment_id):
    """
    Prompts the user to ensure they wish to cancel their appointment
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    response = VoiceResponse()
    appointment = AppointmentTable.objects.get(pk=appointment_id)

    start_time = appointment.start_time
    date = appointment.date

    time_str = start_time.strftime('%I:%M %p')
    date_str = format_date_for_response(date)

    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/cancellation_confirmation/{appointment_id}/")
    gather.say(f"Are you sure you want to cancel your appointment on {date_str} at {time_str}?")
    write_to_log(log, BOT, f"Are you sure you want to cancel your appointment on {date_str} at {time_str}?")
    response.append(gather)
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def cancellation_confirmation(request, appointment_id):
    """
    Get the users response and proceed with the cancellation accordingly
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    response = VoiceResponse()
    speech_result = request.POST.get('SpeechResult', '')
    write_to_log(log, CALLER, speech_result)
    if speech_result:
        declaration = get_response_sentiment(request, speech_result)
        if declaration:
            response.redirect(f"/cancel_appointment/{appointment_id}/")
        else:
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/return_main_menu_response/")
            gather.say("Would you like to go back to the main menu?")
            write_to_log(log, BOT, "Would you like to go back to the main menu?")
            response.append(gather)
    else:
        response.redirect(f"/prompt_cancellation_confirmation/{appointment_id}/")

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def return_main_menu_response(request):
    """
    Route the user back to the main menu or hang up, depending on their response.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    response = VoiceResponse()
    speech_result = request.POST.get('SpeechResult', '')
    write_to_log(log, CALLER, speech_result)

    if speech_result:
        declaration = get_response_sentiment(request, speech_result)
        if declaration:
            response.redirect("/answer/")
        else:
            response.say("Have a great day!")
            write_to_log(log, BOT, "Have a great day!")
            response.hangup()
    else:
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/return_main_menu_response/")
        gather.say("Would you like to go back to the main menu?")
        write_to_log(log, BOT, "Would you like to go back to the main menu?")
        response.append(gather)

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def reroute_no_appointment(request):
    """
    Prompt user for if they would like to go back to the main menu when they do not have an appointment.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    response = VoiceResponse()

    response.say("We do not have an appointment registered with your number.")
    write_to_log(log, BOT, "We do not have an appointment registered with your number.")
    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/return_main_menu_response/")
    gather.say("Would you like to go back to the main menu?")
    write_to_log(log, BOT, "Would you like to go back to the main menu?")
    response.append(gather)
    
    return HttpResponse(str(response), content_type="text/xml")
