from twilio.twiml.voice_response import VoiceResponse, Gather
from .utilities import (appointment_count, get_response_sentiment,
                        get_phone_number)
from django.views.decorators.csrf import csrf_exempt
from ..models import User, AppointmentTable, Log
from django.http import HttpResponse
from openai import OpenAI
from datetime import datetime, timedelta
import calendar
from django.utils.timezone import now
import urllib.parse
from .utilities import (forward_operator, write_to_log, 
                        format_date_for_response, get_day, check_available_date,
                        get_available_times_for_date, send_sms)

BOT = "bot"
CALLER = "caller"
TIMEOUT_LENGTH = 2  # The length of time the bot waits for a response
# TODO: Assuming each appointment is 15 minutes
FIXED_APPT_DURATION = timedelta(minutes=15)


@csrf_exempt
def check_account(request):
    """
    Check the User table for phone number to check if the account exists.
    If it does, relay the information such as the saved name to confirm
    the account.
    """
    # Have twilio send the caller's number using 'From'
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    response = VoiceResponse()

    action = request.GET.get("action", "schedule").lower()

    try:
        if caller_number:
            # Query the User table for phone number and relay saved name.
            user = User.objects.get(phone_number=caller_number)
            if user.first_name != "NaN" and user.last_name != "NaN":
                response.say(f"Hello, {user.first_name} {user.last_name}.")
                write_to_log(log, BOT,
                            f"Hello, {user.first_name} {user.last_name}.")

                # Confirm the account with the caller
                gather = Gather(input="speech", timeout=TIMEOUT_LENGTH,
                                action=f"/confirm_account/?action={action}")

                gather.say("Is this your account? Please say yes or no.")
                write_to_log(log, BOT,
                            "Is this your account? Please say yes or no.")
                response.append(gather)

                # Repeat the prompt if no input received
                response.redirect(f"/check_account/?action={action}")
            else:
                raise User.DoesNotExist
        else:
            # Phone number is invalid
            response.say("Sorry, we are unable to help you at this time.")
            write_to_log(log, BOT,
                         "Sorry, we are unable to help you at this time.")
            forward_operator(log)
    # Inform caller that there wasn't an account found
    except User.DoesNotExist:
        if action == "schedule":

            # User does not exist to being registration process
            gather = Gather(input="speech",
                            timeout=TIMEOUT_LENGTH, action="/get_name/")
            gather.say("Can I get your first and last name please?")
            write_to_log(log, BOT,
                         "Can I get your first and last name please?")
            response.append(gather)

        elif action == "reschedule":
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH,
                            action="/no_account_reroute/")
            gather.say("We do not have an account associated with your number. Would you like to go back to the main menu? Please say yes or no.")
            response.append(gather)

        elif action == "cancel":
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH,
                            action="/no_account_reroute/")
            gather.say("We do not have an account associated with your number. Would you like to go back to the main menu? Please say yes or no.")
            response.append(gather)
        else:
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH,
                            action="/get_name/")
            gather.say("Can I get your first and last name please?")
            response.append(gather)

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def confirm_account(request):
    """
    Process the caller's response. If they say yes, the account is confirmed,
    otherwise they will be prompted to try again.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()

    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    action = request.GET.get("action", "schedule").lower()
    response = VoiceResponse()
    write_to_log(log, CALLER, speech_result)

    declaration = get_response_sentiment(speech_result)

    if declaration:
        response.say("Great! Your account has been confirmed!")
        write_to_log(log, BOT, "Great! Your account has been confirmed!")

        if action == "cancel":
            response.redirect("/cancel_initial_routing/")

        if action == "reschedule":
            if appointment_count(request) > 1:
                # redirect to handle appt > 1 path
                response.redirect("/prompt_reschedule_appointment_over_one/")
            elif appointment_count(request) == 1:
                # redirect to handle appt == 1 path
                date_encoded = None
                response.redirect(f"/reschedule_appointment/{date_encoded}/")
            else:
                # return to main menu if no appointments associated to account
                gather = Gather(input="speech", timeout=TIMEOUT_LENGTH,
                                action="/return_main_menu/")
                gather.say("We do not have an appointment registered with your number. Would you like to go back to the main menu?")
                response.append(gather)

        else:
            response.redirect("/request_date_availability/")
    else:
        response.say("I'm sorry, please try again.")
        write_to_log(log, BOT, "I'm sorry, please try again.")

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def get_name(request):
    """
    Processes the users response to extract their name
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()

    speech_result = request.POST.get('SpeechResult', '')
    response = VoiceResponse()
    write_to_log(log, CALLER, speech_result)

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
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH,
                        action=f"/process_name_confirmation/{name_encoded}/")
        gather.say(f"Your name is {response_pred}. Is that correct?")
        write_to_log(log, BOT,
                     f"Your name is {response_pred}. Is that correct?")
        response.append(gather)
    else:
        response.redirect("/check_account/")

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def process_name_confirmation(request, name_encoded):
    """
    Based on confirmation of name, routes the flow of the conversation.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()

    speech_result = request.POST.get('SpeechResult', '')
    write_to_log(log, CALLER, speech_result)
    confirmation = get_response_sentiment(speech_result)

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
        user, created = User.objects.get_or_create(
            phone_number=caller_number,
            defaults={
                "first_name": "NaN",
                "last_name": "NaN",
            }
        )
        user.first_name = first_name
        user.last_name = last_name
        user.email = None

        user.save()

        # Send to get_date function
        response.redirect("/request_date_availability/")
    else:
        # Add a strike
        response.say("I'm sorry, please try again.")
        write_to_log(log, BOT, "I'm sorry, please try again.")
        response.redirect("/check_account/")

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def request_date_availability(request):
    """
    Ask the caller what day they would like to schedule an appointment.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    response = VoiceResponse()
    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH,
                    action="/check_for_appointment/")
    gather.say("What day are you available for your appointment?")
    write_to_log(log, BOT, "What day are you available for your appointment?")
    response.append(gather)

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def confirm_request_date_availability(request):
    """
    Asks the caller for a confirmation on whether to reprompt them for another
    date availability.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()

    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    write_to_log(log, CALLER, speech_result)
    declaration = get_response_sentiment(speech_result)
    response = VoiceResponse()

    if declaration:
        # Ask for available date again
        response.redirect("/request_date_availability/")
    else:
        # Send user back to the start of loop
        response.redirect("/answer/")

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def confirm_available_date(request):
    """
    Asks the caller for a confirmation on whether to reprompt them for another
    date availability.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    write_to_log(log, CALLER, speech_result)
    declaration = get_response_sentiment(speech_result)
    response = VoiceResponse()
    # Extract appointment date from URL
    appointment_date_str = request.GET.get('date', '')
    # Extract number of available appointments
    number_of_appointments = request.GET.get('num', '0')

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
        # Send user back to ask for another day
        response.redirect("/request_date_availability/")

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def confirm_time_selection(request, time_encoded, date):
    """
    Confirm appointment details
    """
    response = VoiceResponse()

    phone_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=phone_number).last()
    user = User.objects.get(phone_number=phone_number)
    first_name = user.first_name
    last_name = user.last_name
    time = time_encoded
    time_encoded = urllib.parse.quote(time_encoded)

    date_obj = datetime.strptime(date, "%Y-%m-%d")
    date_final = format_date_for_response(date_obj)

    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH,
                    action=f"/final_confirmation/{time_encoded}/{date}/")
    gather.say(f"Great! To confirm you are booked for {date_final} at {time} and your name is {first_name} {last_name}. Is that correct?")
    write_to_log(log, BOT,
                 f"Great! To confirm you are booked for {date_final} at {time} and your name is {first_name} {last_name}. Is that correct?")
    response.append(gather)

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def final_confirmation(request, time_encoded, date):
    """
    If yes, books appointment. If no sends back to main menu.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    response = VoiceResponse()
    speech_result = request.POST.get('SpeechResult', '')
    write_to_log(log, CALLER, speech_result)

    declaration = get_response_sentiment(speech_result)
    if declaration:
        # book appointment
        time_str = time_encoded
        phone_number = get_phone_number(request)

        user = User.objects.get(phone_number=phone_number)

        try:
            appointment_date = datetime.strptime(date, '%Y-%m-%d').date()
            start_time = datetime.strptime(time_str, '%I:%M %p').time()

            start_datetime = datetime.combine(appointment_date, start_time)
            end_datetime = start_datetime + FIXED_APPT_DURATION
            end_time = end_datetime.time()

        except ValueError:
            response.say("An error has occurred when attempting to schedule your appointment.")  # Forward to operator
            write_to_log(log, BOT,
                         "An error has occurred when attempting to schedule your appointment.")
            forward_operator(log)
            return HttpResponse(str(response), content_type="text/xml")

        AppointmentTable.objects.create(
            user=user,
            start_time=start_time,
            end_time=end_time,
            date=appointment_date
        )

        response.say("Perfect! Your appointment has been scheduled. You'll receive a confirmation SMS shortly. Have a great day!")
        write_to_log(log, BOT, "Perfect! Your appointment has been scheduled. You'll receive a confirmation SMS shortly. Have a great day!")
        send_sms(phone_number,f"Your appointment at {start_datetime} has been scheduled. Thank you!")
    else:
        response.redirect("/answer/")

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def get_time_response(request):
    """
    Get's the users time response to the available times listed
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    appointment_date_str = request.GET.get('date', '')
    time_list_encoded = request.GET.get('time_list', '')
    time_list = urllib.parse.unquote(time_list_encoded)

    speech_result = request.POST.get('SpeechResult', '')
    write_to_log(log, CALLER, speech_result)
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
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH,
                        action=f"/given_time_response/{time_encoded}/{appointment_date_str}/")
        gather.say(f"Your requested time was {response_pred}. Is that correct?")
        write_to_log(log, BOT,
                     f"Your requested time was {response_pred}. Is that correct?")
        response.append(gather)
    else:
        response.redirect(f"/request_preferred_time_under_four/?date={appointment_date_str}")

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def given_time_response(request, time_encoded, date):
    """
    Get's the users response for the given times and see's if
    it is satisfactory. Determines the path of the
    conversation based on the users response.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    response = VoiceResponse()
    speech_result = request.POST.get('SpeechResult', '')
    write_to_log(log, CALLER, speech_result)
    declaration = get_response_sentiment(speech_result)

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
    Get's the users response for the suggested time and see's
    if it is satisfactory. Determines the path of the
    conversation based on the users response.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    response = VoiceResponse()

    speech_result = request.POST.get('SpeechResult', '')
    write_to_log(log, CALLER, speech_result)
    declaration = get_response_sentiment(speech_result)
    if declaration:
        # Confirm appointment time
        time_encoded = urllib.parse.quote(time_encoded)
        response.redirect(f"/confirm_time_selection/{time_encoded}/{date}/")
    else:
        # Ask for a different time
        response.redirect(f"/request_preferred_time_over_three/?date={date}")

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def check_for_appointment(request):
    """
    Searches appointment table for an available day that
    the caller requested.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()

    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    write_to_log(log, CALLER, speech_result)
    speech_result = get_day(speech_result)
    speech_result = speech_result.lower()

    weekdays = {day.lower(): index for index, day in enumerate(calendar.day_name)}

    if speech_result not in weekdays:
        response = VoiceResponse()
        response.say("I did not recognize that day. Can you say a weekday like Monday or Friday?")
        write_to_log(log, BOT,
                     "I did not recognize that day. Can you say a weekday like Monday or Friday?")
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH,
                        action="/check_for_appointment/")
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
        write_to_log(log, BOT, f"The next available {speech_result.capitalize()} is at {appointment_date.strftime('%B %d, %Y')}. Does that work for you?")
        response.append(gather)
    else:
        response.say(f"Sorry, no available days on {speech_result.capitalize()} for the next month. Would you like to choose another day?")
        write_to_log(log, BOT, f"Sorry, no available days on {speech_result.capitalize()} for the next month. Would you like to choose another day?")
        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action="/confirm_request_date_availability/")
        response.append(gather)

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def request_preferred_time_under_four(request):
    """
    Ask the caller what time they would like to schedule if there are
    <= 3 available times.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    response = VoiceResponse()

    # Extract appointment_date from the request
    appointment_date_str = request.GET.get('date', '')

    try:
        appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
    except ValueError:
        response.say("There was an issue retrieving the appointment date. Please try again.")
        write_to_log(log, BOT, "There was an issue retrieving the appointment date. Please try again.")
        response.redirect("/request_date_availability/")
        return HttpResponse(str(response), content_type="text/xml")

    available_times = get_available_times_for_date(appointment_date)

    if available_times:
        formatted_times = [t.strftime('%I:%M %p') for t in available_times]
        time_list_text = ', '.join(formatted_times[:-1]) + f", and {formatted_times[-1]}" if len(formatted_times) > 1 else formatted_times[0]
        time_list_encoded = urllib.parse.quote(time_list_text)

        gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/get_time_response/?date={appointment_date_str}&time_list={time_list_encoded}", method="POST")
        gather.say(f"Here are the available times for {appointment_date.strftime('%B %d')}: {time_list_text}. Which time would you like?")
        write_to_log(log, BOT, f"Here are the available times for {appointment_date.strftime('%B %d')}: {time_list_text}. Which time would you like?")
        response.append(gather)
    else:
        response.say("There are no available times on this day. Would you like to choose another day?")
        write_to_log(log, BOT, "There are no available times on this day. Would you like to choose another day?")
        response.redirect("/request_date_availability/")

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def request_preferred_time_over_three(request):
    """
    Ask the caller what time they would like to schedule if there are
    > 3 available times.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    # Extract appointment_date from the request
    appointment_date_str = request.GET.get('date', '')
    response = VoiceResponse()

    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/generate_requested_time/?date={appointment_date_str}")
    gather.say("What time would you like?")
    write_to_log(log, BOT, "What time would you like?")
    response.append(gather)

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def generate_requested_time(request):
    """
    Uses GPT to generate a most-likely time that the caller asked for.
    """
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    speech_result = request.POST.get('SpeechResult', '')
    write_to_log(log, CALLER, speech_result)
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
        write_to_log(log, BOT, f"Your requested time was {response_pred}. Is that correct?")
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
    caller_number = get_phone_number(request)
    log = Log.objects.filter(phone_number=caller_number).last()
    speech_result = request.POST.get('SpeechResult', '')
    write_to_log(log, CALLER, speech_result)
    confirmation = get_response_sentiment(speech_result)
    response = VoiceResponse()
    # Extract appointment_date from the request
    appointment_date_str = request.GET.get('date', '')

    try:
        appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
    except ValueError:
        response.say("There was an issue retrieving the appointment date. Please try again.")
        write_to_log(log, BOT, "There was an issue retrieving the appointment date. Please try again.")
        response.redirect("/request_date_availability/")
        return HttpResponse(str(response), content_type="text/xml")

    if confirmation:
        requested_time_str = urllib.parse.unquote(time_encoded)
        available_times = get_available_times_for_date(appointment_date)

        try:
            requested_time = datetime.strptime(requested_time_str, '%I:%M %p').time()
        except ValueError:
            response.say("There was an issue understanding your requested time. Please try again.")
            write_to_log(log, BOT, "There was an issue understanding your requested time. Please try again.")
            response.redirect("/request_preferred_time_over_three/")
            return HttpResponse(str(response), content_type="text/xml")

        if not available_times:
            response.say(f"Sorry, there are no available appointments on {appointment_date.strftime('%B %d, %Y')}.")
            write_to_log(log, BOT, f"Sorry, there are no available appointments on {appointment_date.strftime('%B %d, %Y')}.")
            response.redirect("/request_date_availability/")
            return HttpResponse(str(response), content_type="text/xml")

        if requested_time in available_times:
            time_encoded_url = urllib.parse.quote(time_encoded)
            response.redirect(f"/confirm_time_selection/{time_encoded_url}/{appointment_date_str}/")
        else:
            # TODO: the lines below handles nearest appointment time, potentially put in its own separate function?
            nearest_time = min(available_times, key=lambda t: abs(datetime.combine(appointment_date, t) - datetime.combine(appointment_date, requested_time)))

            response.say(f"Our nearest appointment slot is {nearest_time.strftime('%I:%M %p')}. Does that work for you?")
            write_to_log(log, BOT, f"Our nearest appointment slot is {nearest_time.strftime('%I:%M %p')}. Does that work for you?")
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH, action=f"/suggested_time_response/{urllib.parse.quote(nearest_time.strftime('%I:%M %p'))}/{appointment_date_str}/", method="POST")
            gather.say("Please say yes to confirm or no to select another time.")
            write_to_log(log, BOT, "Please say yes to confirm or no to select another time.")
            response.append(gather)

    else:
        response.redirect(f"/request_preferred_time_over_three/?date={appointment_date_str}")

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def cancel_appointment(request, appointment_id):
    """
    Cancels the caller's appointment and informs them their appointment has been canceled.
    """
    response = VoiceResponse()
    
    try: 
        appt_to_cancel = AppointmentTable.objects.get(pk=appointment_id)
    except AppointmentTable.DoesNotExist:
        response.say("We could not find an appointment to cancel.")
        response.redirect("/answer/") # Reroute back to main menu if no appointment found
        return HttpResponse(str(response), content_type="text/xml")
    
    appt_date = appt_to_cancel.date.strftime("%B %d") # Formatted like "March 03"
    appt_time = appt_to_cancel.start_time.strftime("%I:%M %p") # Formatted like "10:30 AM"

    # Get the phone number associated with the appointment's user
    phone_number = appt_to_cancel.user.phone_number if appt_to_cancel.user else None

    appt_to_cancel.delete() # Delete the appointment

    cancellation_message = f"Your appointment on {appt_date} at {appt_time} has been canceled. Thank you!"

    if phone_number:
        try: 
            send_sms(phone_number, cancellation_message)
        except Exception as e:
            print(f"Error sending SMS: {e}") 

    response.say(cancellation_message)
    response.hangup()

    return HttpResponse(str(response), content_type="text/xml")


def reroute_caller_with_no_account(request):
    """
    Check the User table for phone number to check if the account exists.
    If it doesn't, reroute the caller to main menu or hang up according to
    their response
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
    Helper function for reroute_caller_with_no_account to handle response from
    caller. If the response is yes, reroute to the main menu.
    If the response is no, hang up the call.
    """
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    response = VoiceResponse()
    declaration = get_response_sentiment(speech_result)

    if declaration:
        # If user said yes, redirect to main menu (in this example /answer/)
        response.say("Returning you to the main menu.")
        response.redirect("/answer/")
    else:
        # If user said no (or another negative response), hang up
        response.say("Thank you for calling, Goodbye.")
        response.hangup()

    return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
def reschedule_appointment(request, date_encoded):
    """
    Reschedule appointment for the caller by cancelling an upcoming
    appointment, informing the caller and then redirecting to the
    scheduling flow to book a new appointment.
    """
    response = VoiceResponse()
    phone_number = get_phone_number(request)

    if not phone_number:
        response.say("Sorry, we were unable to help you at this time.")
        response.hangup()
        return HttpResponse(str(response), content_type="text/xml")

    try:
        user = User.objects.get(phone_number=phone_number)
    except User.DoesNotExist:
        response.redirect("/reroute_caller_with_no_account/")
        return HttpResponse(str(response), content_type="text/xml")

    upcoming_appts = list(AppointmentTable.objects.filter(user=user, date__gte=now().date()).order_by('date'))
    num_appts = len(upcoming_appts)
    if num_appts == 0:
        response.say("You do not have an appointment scheduled.")
        response.say("Let's schedule a new appointment.")
        response.redirect("/request_date_availability/")
        return HttpResponse(str(response), content_type="text/xml")

    if num_appts == 1:
        appt_to_cancel = upcoming_appts[0]  # Cancel the only appt that exists

    else:
        if not date_encoded:
            response.say("No appointment date specified for rescheduling")
            response.hangup()
            return HttpResponse(str(response), content_type="text/xml")
        try:
            decoded_date_str = urllib.parse.unquote(date_encoded)
            target_date = datetime.strptime(decoded_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            response.say("Invalid appointment date provided.")
            response.hangup()
            return HttpResponse(str(response), content_type="text/xml")

        appt_to_cancel = next((appt for appt in upcoming_appts if appt.date.date() == target_date), None)
        if not appt_to_cancel:
            response.say("No appointment found on the specified date.")
            response.hangup()
            return HttpResponse(str(response), content_type="text/xml")

    appt_to_cancel.delete()
    response.say("Your appointment has been canceled.")
    response.say("Let's schedule a new appointment.")

    appt_date = appt_to_cancel.date.strftime("%B %d") # Formatted like "March 03"
    appt_time = appt_to_cancel.start_time.strftime("%I:%M %p") # Formatted like "10:30 AM"

    cancellation_message = f"Your appointment on {appt_date} at {appt_time} has been canceled. Thank you!"

    if phone_number:
        try: 
            send_sms(phone_number, cancellation_message)
        except Exception as e:
            print(f"Error sending SMS: {e}")

    response.redirect("/request_date_availability/")

    return HttpResponse(str(response), content_type="text/xml")
