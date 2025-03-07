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

TIMEOUT_LENGTH = 3 # The length of time the bot waits for a response
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
    response = VoiceResponse()

    if declaration:
        response.redirect("/request_date_availability/") # Ask for available date again
    else:
        response.redirect("/prompt_question/") # Send user back to the start of loop

@csrf_exempt
def confirm_available_date(request):
    """
    Asks the caller for a confirmation on whether to reprompt them for another
    date availability.
    """
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    declaration = get_response_sentiment(request, speech_result)
    response = VoiceResponse()

    if declaration:
        pass
        #response.redirect("") TODO: redirect to schedule a time
    else:
        response.redirect("/request_date_availability/") # Send user back to ask for another day

@csrf_exempt
def check_for_appointment(request):
    """
    Searches appointment table for an available day that
    the caller requested.
    """
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    weekdays = {day.lower(): index for index, day in enumerate(calendar.day_name)}

    if speech_result not in weekdays:
        response = VoiceResponse()
        response.say("I did not recognize that day. Can you say a weekday like Monday or Friday?")
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/check_for_appointment/")
        response.append(gather)
        return HttpResponse(str(response), content_type="text/xml")

    target_weekday = weekdays[speech_result]

    # Check if there are time slots on that day
    is_available, appointment_date, number_available_appointments = check_available_date(target_weekday)

    response = VoiceResponse()
    if is_available:
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/confirm_available_date/", method="POST")
        gather.say(f"The next available {speech_result.capitalize()} is at {appointment_date.strftime('%B %d, %Y')}. Does that work for you?")
        response.append(gather)
    else:
        response.say(f"Sorry, no available days on {speech_result.capitalize()} for the next month. Would you like to choose another day?")
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/confirm_request_date_availability/")
        response.append(gather)

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def check_available_date(target_weekday):
    """
    Return if the given date has available timeslots or not.
    """
    today = now().date()
    max_weeks_ahead = 4 
    number_available_appointments = 0

    for week in range(max_weeks_ahead):
        # Calculate the next occurrence of the requested weekday
        days_ahead = (target_weekday - today.weekday()) % 7
        if days_ahead == 0 and week == 0:
            days_ahead = 7 

        appointment_date = today + timedelta(days=days_ahead + (week * 7))

        # Retrieve existing appointments for this date
        existing_appointments = AppointmentTable.objects.filter(date__date=appointment_date).order_by('start_time')

        # For no appointments that day yet
        if not existing_appointments:
            number_available_appointments = 4 # TODO: mod by n = fixed appt. length
            return True, appointment_date, number_available_appointments

        current_time = EARLIEST_TIME

        # Check for time slots in between appointments or after all appointments
        for appointment in existing_appointments:
            if current_time < appointment.start_time:
                number_available_appointments += 1
            current_time = appointment.end_time

        if current_time < LATEST_TIME:
            number_available_appointments += 1  # TODO: mod by n = fixed appt. length
        
        # If there are available timeslots return True and additional var.
        if number_available_appointments > 0:
            return True, appointment_date, number_available_appointments

    # If no available timeslots for the next month on request day return False    
    return False, None, 0