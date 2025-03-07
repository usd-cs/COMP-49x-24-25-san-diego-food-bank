from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from .phone_service_faq import get_response_sentiment, prompt_question
from django.views.decorators.csrf import csrf_exempt
from ..models import User, AppointmentTable
from django.http import HttpResponse
from openai import OpenAI
from datetime import time, datetime, timedelta
import calendar
from django.utils.timezone import now
import urllib.parse
import re

TIMEOUT_LENGTH = 3 # The length of time the bot waits for a response
EARLIEST_TIME = time(9, 0)   # Earliest time to schedule an appointment, 9:00 AM
LATEST_TIME = time(17, 0)    # Latest time appointments can end, 5:00 PM
# FIXED_APPT_DURATION = TODO

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
        if caller_number:
            # Query the User table for phone number and relay saved name.
            user = User.objects.get(phone_number=caller_number)
            response.say(f"Hello, {user.first_name} {user.last_name}.")

            # Confirm the account with the caller 
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/confirm_account/")
            gather.say("Is this your account? Please say yes or no.")
            response.append(gather)

            # Repeat the prompt if no input received
            response.redirect("/check_account/")
        else:
            # Phone number is invalid
            response.say("Sorry, we are unable to help you at this time.")
    # Inform caller that there wasn't an account found
    except User.DoesNotExist:
        # User does not exist to being registration process
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/get_name/")
        gather.say("Can I get your first and last name please?")
        response.append(gather)
    
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
        response.redirect("/prompt_question/") # Replace with get_date later
    else:
        response.say("I'm sorry, please try again.")
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def get_name(request):
    """
    Processes the users response to extract their name
    """
    speech_result = request.POST.get('SpeechResult', '')
    response = VoiceResponse()
    
    if speech_result:
        # Query GPT for name (incase other words are said)
        client = OpenAI()
        system_prompt = "Please extract someones first and last name from the following message. Only respond with the first and last name."
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": speech_result}
            ]
        )   
        response_pred = completion.choices[0].message.content

        name_encoded = urllib.parse.quote(response_pred)
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/process_name_confirmation/{name_encoded}/")
        gather.say(f"Your name is {response_pred}. Is that correct?")
        response.append(gather)
    else:
        response.redirect("/check_account/")
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def process_name_confirmation(request, name_encoded):
    """
    Based on confirmation of name, routes the flow of the conversation.
    """
    speech_result = request.POST.get('SpeechResult', '')
    confirmation = get_response_sentiment(request, speech_result)
    
    response = VoiceResponse()
    if confirmation:
        # Unencode the name and split into first and last name
        name = urllib.parse.unquote(name_encoded)
        name = name.split()

        first_name = name[0]
        last_name = None
        if len(name) >= 2:
            last_name = name[-1]
        else:
            last_name = ""

        caller_number = get_phone_number(request)

        # Create user account
        new_user = User.objects.create(
                first_name=first_name,
                last_name=last_name,
                phone_number=caller_number,
        )

        # Send to get_date function
        response.say("Rerouting to get date.") # Place holder
    else:
        # Add a strike
        response.say("I'm sorry, please try again.")
        response.redirect("/check_account/")
    
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
        response.redirect("/answer/") # Send user back to the start of loop

@csrf_exempt
def confirm_available_date(request):
    """
    Asks the caller for a confirmation on whether to reprompt them for another
    date availability.
    """
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    declaration = get_response_sentiment(request, speech_result)
    response = VoiceResponse()
    appointment_date_str = request.GET.get('date', '')  # Extract appointment date from URL
    number_of_appointments = request.GET.get('num', '0')  # Extract number of available appointments

    try:
        number_of_appointments = int(number_of_appointments)
    except ValueError:
        number_of_appointments = 0

    if declaration:
        if number_of_appointments > 3:
            response.redirect(f"/request_preferred_time_over_three/?date={appointment_date_str}")
        else: 
            response.redirect(f"/request_preferred_time_under_four/?date={appointment_date_str}")
    else:
        response.redirect("/request_date_availability/") # Send user back to ask for another day

@csrf_exempt
def confirm_time_selection(request):
    #TODO: kieran's function delete if not needed
    pass

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
        action_url = f"/confirm_available_date/?date={appointment_date}&num={number_available_appointments}"
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=action_url, method="POST")
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

@csrf_exempt
def request_preferred_time_under_four(request):
    """
    Ask the caller what time they would like to schedule if there are
    <= 3 available times.
    """
    response = VoiceResponse()
    
    # Extract appointment_date from the request
    appointment_date_str = request.GET.get('date', '')

    try:
        appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
    except ValueError:
        response.say("There was an issue retrieving the appointment date. Please try again.")
        response.redirect("/request_date_availability/")
        return HttpResponse(str(response), content_type="text/xml")
    
    available_times = get_available_times_for_date(appointment_date)

    if available_times:
        formatted_times = [t.strftime('%I:%M %p') for t in available_times]
        time_list_text = ', '.join(formatted_times[:-1]) + f", and {formatted_times[-1]}" if len(formatted_times) > 1 else formatted_times[0]

        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/confirm_time_selection/?date={appointment_date_str}", method="POST")
        gather.say(f"Here are the available times for {appointment_date.strftime('%B %d')}: {time_list_text}. Which time would you like?")
        response.append(gather)
    else:
        response.say("There are no available times on this day. Would you like to choose another day?")
        response.redirect("/request_date_availability/")

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def request_preferred_time_over_three(request):
    """
    Ask the caller what time they would like to schedule if there are
    > 3 available times.
    """
    # Extract appointment_date from the request
    appointment_date_str = request.GET.get('date', '')
    response = VoiceResponse()
    
    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/generate_requested_time/?date={appointment_date_str}")
    gather.say("What time would you like?")
    response.append(gather)

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def generate_requested_time(request):
    """
    Uses GPT to generate a most-likely time that the caller asked for.
    """
    speech_result = request.POST.get('SpeechResult', '')
    response = VoiceResponse()
    # Extract appointment_date from the request
    appointment_date_str = request.GET.get('date', '')
    
    if speech_result:
        # Query GPT for time to be able to cover statement variations
        client = OpenAI()
        system_prompt = "Please give the most likely intended time from the following message. Consider that business hours are during 9:00 AM and 5:00 PM. Make sure it is in a format like 4:59 PM."
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": speech_result}
            ]
        )   
        response_pred = completion.choices[0].message.content

        time_encoded = urllib.parse.quote(response_pred)
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/find_requested_time/{time_encoded}/?date={appointment_date_str}")
        gather.say(f"Your requested time was {response_pred}. Is that correct?")
        response.append(gather)
    else:
        response.redirect(f"/request_preferred_time_over_three/?date={appointment_date_str}")
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def find_requested_time(request, time_encoded):
    """
    Uses the GPT generated time request to find appointments that match exactly
    or are closest to that time request.
    """
    speech_result = request.POST.get('SpeechResult', '')
    confirmation = get_response_sentiment(request, speech_result)
    response = VoiceResponse()
    # Extract appointment_date from the request
    appointment_date_str = request.GET.get('date', '')

    try:
        appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
    except ValueError:
        response.say("There was an issue retrieving the appointment date. Please try again.")
        response.redirect("/request_date_availability/")
        return HttpResponse(str(response), content_type="text/xml")

    if confirmation:
        requested_time_str = urllib.parse.unquote(time_encoded)
        available_times = get_available_times_for_date(appointment_date)

        try:
            requested_time = datetime.strptime(requested_time_str, '%I:%M %p').time()
        except ValueError:
            response.say("There was an issue understanding your requested time. Please try again.")
            response.redirect("/request_preferred_time_over_three/")
            return HttpResponse(str(response), content_type="text/xml")
        
        if not available_times:
            response.say(f"Sorry, there are no available appointments on {appointment_date.strftime('%B %d, %Y')}.")
            response.redirect("/request_date_availability/")
            return HttpResponse(str(response), content_type="text/xml")

        if requested_time in available_times:
            response.say(f"Your appointment has been scheduled for {appointment_date.strftime('%B %d, %Y')} at {requested_time.strftime('%I:%M %p')}.")
            # TODO: Save the appointment in the database here
        else:
            # TODO: the lines below handles nearest appointment time, potentially put in its own separate function?
            nearest_time = min(available_times, key=lambda t: abs(datetime.combine(appointment_date, t) - datetime.combine(appointment_date, requested_time)))

            response.say(f"Our nearest appointment slot is {nearest_time.strftime('%I:%M %p')}. Does that work for you?")
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/confirm_time_selection/?date={appointment_date_str}&time={urllib.parse.quote(nearest_time.strftime('%I:%M %p'))}", method="POST")
            gather.say("Please say yes to confirm or no to select another time.")
            response.append(gather)
    
    else:
        response.redirect(f"/request_preferred_time_over_three/?date={appointment_date_str}")    
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def get_available_times_for_date(appointment_date):
    """
    Retrieve available appointment times for a given date.
    """
    existing_appointments = AppointmentTable.objects.filter(date__date=appointment_date).order_by('start_time')
    available_times = []

    current_time = EARLIEST_TIME
    for appointment in existing_appointments:
        if current_time < appointment.start_time:
            available_times.append(current_time)
        current_time = appointment.end_time

    if current_time < LATEST_TIME:
        available_times.append(current_time) #TODO: add timeslots mod by fixed appt. time

    return available_times