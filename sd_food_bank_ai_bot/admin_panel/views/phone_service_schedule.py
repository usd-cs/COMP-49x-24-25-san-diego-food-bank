from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from .phone_service_faq import get_response_sentiment, prompt_question
from django.views.decorators.csrf import csrf_exempt
from ..models import User, AppointmentTable
from django.http import HttpResponse
from openai import OpenAI
from datetime import time, datetime, timedelta
import calendar
from django.utils.timezone import now
import re


TIMEOUT_LENGTH = 2 # The length of time the bot waits for a response
EARLIEST_TIME = time(9, 0)   # Earliest time to schedule an appointment, 9:00 AM
LATEST_TIME = time(17, 0)    # Latest time appointments can end, 5:00 PM

@csrf_exempt
def get_phone_number(request):
    """
    Gets the user phone number from the post header
    """
    caller_number = request.POST.get('From', '')

    #regex check
    expression = "^\+[1-9]\d{1,14}$" # E.164 compliant phone numbers
    valid = re.match(expression, caller_number)
    
    if valid:
        return caller_number
    return None

@csrf_exempt
def check_account(request):
    """
    Check the User table for phone number to check if the account exists. If it does, 
    relay the information such as the saved name to confirm the account.
    """
    # Have twilio send the caller's number using 'From'
    caller_number = get_phone_number(request)
    response = VoiceResponse()
    try: 
        # Query the User table for phone number and relay saved name.
        user = User.objects.get(phone_number=caller_number)
        response.say(f"Hello, {user.first_name} {user.last_name}.")

        # Confirm the account with the caller 
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/confirm_account/")
        gather.say("Is this your account? Please say yes or no.")
        response.append(gather)

        # Repeat the prompt if no input received
        response.redirect("/check_account/") 
    # Inform caller that there wasn't an account found
    except User.DoesNotExist:
        response.say("I'm sorry. We did not find an account associated with this phone number.") # Later change prompt and send to account registration
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def confirm_account(request):
    """
    Process the caller's response. If they say yes, the account is confirmed, otherwise
    they will be prompted to try again.
    """
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    response = VoiceResponse()

    declaration = get_response_sentiment(request, speech_result)

    if declaration:
        response.say("Great! Your account has been confirmed!")
        response.redirect("/prompt_question/")
    else:
        response.say("I'm sorry, please try again.")
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def request_date_availability(request):
    """
    Ask the caller what day they would like to schedule an appointment.
    """
    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/check_for_appointment/")
    gather.say("What day are you available for your appointment?")

@csrf_exempt
def confirm_request_date_availability(request):
    """
    Asks the caller for a confirmation on whether to reprompt them for another
    date availability.
    """
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    declaration = get_response_sentiment(request, speech_result)

    if declaration:
        request_date_availability(request) # Ask for available date again
    else:
        prompt_question(request) # Send user back to the start of loop

@csrf_exempt
def check_for_appointment(request):
    """
    Searches appointment table for soonest available appointment on a day then
    returns the user with that apppointment.

    TODO: Need to add feature where it handles the user asking for a specific time (instead of being
    put to the soonest available time.)
    """
    speech_result= request.POST.get('SpeechResult', '').strip().lower()

    today = now().date()
    weekdays = {day.lower(): index for index, day in enumerate(calendar.day_name)}

    if speech_result not in weekdays:
        response = VoiceResponse()
        response.say("I didn't recognize that day. Can you say a weekday like Monday or Friday?")
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/check_for_appointment/")
        response.append(gather)
        return HttpResponse(str(response), content_type="text/xml")

    # Get the next occurrence of the requested weekday
    target_weekday = weekdays[speech_result]
    days_ahead = (target_weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7  # If today is the same day, schedule for next week

    appointment_date = today + timedelta(days=days_ahead)

    # Retrieve existing appointments for the selected date
    existing_appointments = AppointmentTable.objects.filter(date__date=appointment_date).order_by('start_time')

    # Find the soonest available time slot
    available_time = find_next_available_time(existing_appointments)

    response = VoiceResponse()
    if available_time:
        response.say(f"The soonest available appointment on {speech_result.capitalize()} is at {available_time.strftime('%I:%M %p')}. Would you like to book it?")
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/confirm_appointment/", method="POST")
        gather.say("Say yes to confirm or no to choose another time.")
        response.append(gather)
    else:
        response.say(f"Sorry, no available times on {speech_result.capitalize()}. Would you like to choose another day?")
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/confirm_request_date_availability/")
        response.append(gather)

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def find_next_available_time(existing_appointments):
    """
    Find the soonest available appointment time on specific day based on existing scheduled appointments.
    """
    if not existing_appointments:
        # No appointments exist, return the earliest available time
        return EARLIEST_TIME

    # Start checking from the beginning of the workday
    current_time = EARLIEST_TIME

    for appointment in existing_appointments:
        if current_time < appointment.start_time:
            # Found a gap before this appointment
            return current_time
        # Move to the end of the current appointment
        current_time = appointment.end_time

    # If all appointments are back-to-back, check if there's room at the end of the day
    if current_time < LATEST_TIME:
        return current_time

    return None  # No available slots