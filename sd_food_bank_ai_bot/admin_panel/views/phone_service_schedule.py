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

TIMEOUT_LENGTH = 5 # The length of time the bot waits for a response
EARLIEST_TIME = time(9, 0)   # Earliest time to schedule an appointment, 9:00 AM
LATEST_TIME = time(17, 0)    # Latest time appointments can end, 5:00 PM
FIXED_APPT_DURATION = timedelta(minutes=15) # TODO: Assuming each appointment is 15 minutes

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

    action = request.GET.get("action", "schedule").lower()

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
        if action == "schedule":

        # User does not exist to being registration process
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/get_name/")
            gather.say("Can I get your first and last name please?")
            response.append(gather)

        elif action == "cancel":
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/no_account_reroute/")
            gather.say("We do not have an account associated with your number. Would you like to go back to the main menu? Please say yes or no.")
            response.append(gather)
        else:
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
        response.redirect("/request_date_availability/")
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
                email=None
        )

        # Send to get_date function
        response.redirect("/request_date_availability/")
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
    response = VoiceResponse()
    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/check_for_appointment/")
    gather.say("What day are you available for your appointment?")
    response.append(gather)

    return HttpResponse(str(response), content_type="text/xml")

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
    
    return HttpResponse(str(response), content_type="text/xml")

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
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def confirm_time_selection(request, time_encoded, date):
    """
    Confirm appointment details
    """
    response = VoiceResponse()

    phone_number = get_phone_number(request)
    user = User.objects.get(phone_number=phone_number)
    first_name = user.first_name
    last_name = user.last_name
    time = time_encoded
    time_encoded = urllib.parse.quote(time_encoded)

    # format date correctly
    date_obj = datetime.strptime(date, "%Y-%m-%d")
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

    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/final_confirmation/{time_encoded}/{date}/")
    gather.say(f"Great! To confirm you are booked for {date_final} at {time} and your name is {first_name} {last_name}. Is that correct?")
    response.append(gather)

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def final_confirmation(request, time_encoded, date):
    """
    If yes, books appointment. If no sends back to main menu.
    """
    response = VoiceResponse()
    speech_result = request.POST.get('SpeechResult', '')

    declaration = get_response_sentiment(request, speech_result)
    if declaration:
        #book appointment
        time_str = time_encoded
        phone_number = get_phone_number(request)
        
        user = User.objects.get(phone_number=phone_number)

        try:
            appointment_date = datetime.strptime(date, '%Y-%m-%d').date()
            start_time = datetime.strptime(time_str, '%I:%M %p').time()

            start_datetime = datetime.combine(appointment_date, start_time)
            end_datetime = start_datetime + timedelta(minutes=30)
            end_time = end_datetime.time()

        except ValueError:
            response.say("An error has occurred when attempting to schedule you appointment.") # Forward to operator
            return HttpResponse(str(response), content_type="text/xml")

        new_appointment = AppointmentTable.objects.create(
            user=user,
            start_time=start_time,
            end_time=end_time,
            date=appointment_date
        )

        response.say("Perfect! Your appointment has been scheduled. You'll receive a confirmation SMS shortly. Have a great day!")
        # send sms
    else:
        response.redirect("/answer/")
    
    return HttpResponse(str(response), content_type="text/xml") 

@csrf_exempt
def get_time_response(request):
    """
    Get's the users time response to the available times listed
    """
    appointment_date_str = request.GET.get('date', '')
    time_list_encoded = request.GET.get('time_list', '')
    time_list = urllib.parse.unquote(time_list_encoded)

    speech_result = request.POST.get('SpeechResult', '')
    response = VoiceResponse()
    
    if speech_result:
        # Query GPT for time to be able to cover statement variations
        client = OpenAI()
        system_prompt = f"Please give the most likely intended time from the following message. Consider the options given were {time_list}"
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": speech_result}
            ]
        )   
        response_pred = completion.choices[0].message.content

        time_encoded = urllib.parse.quote(response_pred)
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/given_time_response/{time_encoded}/{appointment_date_str}/")
        gather.say(f"Your requested time was {response_pred}. Is that correct?")
        response.append(gather)
    else:
        response.redirect(f"/request_preferred_time_under_four/?date={appointment_date_str}")
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def given_time_response(request, time_encoded, date):
    """
    Get's the users response for the given times and see's if it is satisfactory.
    Determines the path of the conversation based on the users response.
    """
    response = VoiceResponse()
    speech_result = request.POST.get('SpeechResult', '')
    declaration = get_response_sentiment(request, speech_result)

    time_encoded = urllib.parse.quote(time_encoded)

    if declaration:
        # Confirm appointment time
        response.redirect(f"/confirm_time_selection/{time_encoded}/{date}/")
    else:
        # Ask for a different time
        response.redirect(f"/request_preferred_time_under_four/?date={date}")

    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def suggested_time_response(request, time_encoded, date):
    """
    Get's the users response for the suggested time and see's if it is satisfactory.
    Determines the path of the conversation based on the users response.
    """
    response = VoiceResponse()

    speech_result = request.POST.get('SpeechResult', '')
    declaration = get_response_sentiment(request, speech_result)
    if declaration:
        # Confirm appointment time
        time_encoded = urllib.parse.quote(time_encoded)
        response.redirect(f"/confirm_time_selection/{time_encoded}/{date}/")
    else:
        # Ask for a different time
        response.redirect(f"/request_preferred_time_over_three/?date={date}")

    return HttpResponse(str(response), content_type="text/xml")

def get_day(request, speech_result):
    """
    Extracts the day of the week from a given message. Only returns the day or NONE.
    """
    client = OpenAI()
    system_prompt = "Please extract the day of the week from the following message. Only respond with the day of the week or NONE if one is not said."
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": speech_result}
        ]
    )   
    response_pred = completion.choices[0].message.content
    
    return response_pred

@csrf_exempt
def check_for_appointment(request):
    """
    Searches appointment table for an available day that
    the caller requested.
    """
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    speech_result = get_day(request, speech_result)
    speech_result = speech_result.lower()

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

        # Check for time slots before appointments until the latest appointment
        for appointment in existing_appointments:
            while current_time < appointment.start_time:
                number_available_appointments += 1
                # Increment by fixed appt time
                current_time = (datetime.combine(datetime.today(), current_time) + FIXED_APPT_DURATION).time()
            current_time = appointment.end_time

        # Checks for time slots after last appointment is iterated in the for loop above
        while current_time < LATEST_TIME:
            number_available_appointments += 1
            current_time = (datetime.combine(datetime.today(), current_time) + FIXED_APPT_DURATION).time()
        
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
        time_list_encoded = urllib.parse.quote(time_list_text)

        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/get_time_response/?date={appointment_date_str}&time_list={time_list_encoded}", method="POST")
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
            response.redirect(f"/confirm_time_selection/{time_encoded}/{appointment_date_str}")
        else:
            # TODO: the lines below handles nearest appointment time, potentially put in its own separate function?
            nearest_time = min(available_times, key=lambda t: abs(datetime.combine(appointment_date, t) - datetime.combine(appointment_date, requested_time)))

            response.say(f"Our nearest appointment slot is {nearest_time.strftime('%I:%M %p')}. Does that work for you?")
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/suggested_time_response/{urllib.parse.quote(nearest_time.strftime('%I:%M %p'))}/{appointment_date_str}/", method="POST")
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
    
    # Adds timeslots between appointments
    for appointment in existing_appointments:
        if current_time < appointment.start_time:
            available_times.append(current_time)
            # Increment by fixed appt time
            current_time = (datetime.combine(datetime.today(), current_time) + FIXED_APPT_DURATION).time()
        current_time = appointment.end_time

    # Adds timeslots after the latest iterated appointment
    while current_time < LATEST_TIME:
        available_times.append(current_time)
        current_time = (datetime.combine(datetime.today(), current_time) + FIXED_APPT_DURATION).time()

    return available_times

@csrf_exempt
def reroute_caller_with_no_account(request):
    """
    Check the User table for phone number to check if the account exists. If it doesn't, 
    reroute the caller to main menu or hang up according to their response
    """
    # Have twilio send the caller's number using 'From'
    caller_number = get_phone_number(request)
    response = VoiceResponse()

    if not caller_number:
        # Phone number is invalid 
        response.say("Sorry, we are unable to help you at this time.")
        return HttpResponse(str(response), content_type="text/xml")

    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/no_account_reroute/")
    gather.say("We do not have an account associated with your number. Would you like to go back to the main menu? Please say yes or no.")
    response.append(gather)
    
    return HttpResponse(str(response), content_type="text/xml")

@csrf_exempt
def no_account_reroute(request):
    """
    Helper function for reroute_caller_with_no_account to handle response from caller.
    If the response is yes, reroute to the main menu. 
    If the response is no, hang up the call.
    """
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    response = VoiceResponse()
    declaration = get_response_sentiment(request, speech_result)

    if declaration:
        # If user said yes, redirect to main menu (in this example /answer/)
        response.say("Returning you to the main menu.")
        response.redirect("/answer/")
    else:
        # If user said no (or another negative response), hang up
        response.say("Thank you for calling, goodbye.")
        response.hangup()

    return HttpResponse(str(response), content_type="text/xml")

