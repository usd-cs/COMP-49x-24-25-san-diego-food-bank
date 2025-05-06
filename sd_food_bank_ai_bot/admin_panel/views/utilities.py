from twilio.twiml.voice_response import VoiceResponse, Dial
from ..models import User, AppointmentTable, FAQ
from django.http import HttpResponse
from twilio.rest import Client
from django.conf import settings
from openai import OpenAI
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from datetime import time, datetime, timedelta
from google.cloud import translate_v2 as translate
import re

# Earliest time to schedule an appointment, 9:00 AM
EARLIEST_TIME = time(9, 0)
LATEST_TIME = time(17, 0)    # Latest time appointments can end, 5:00 PM
# TODO: Assuming each appointment is 15 minutes
FIXED_APPT_DURATION = timedelta(minutes=15)


def strike_system_handler(log, reset=False):
    """
    Updates strikes within the log object associated with call as
    conversation progresses
    """
    if log:
        if reset:
            log.reset_strikes()
        else:

            if log.add_strike():
                forward_operator(log)


def get_phone_number(request):
    """
    Gets the user phone number from the post header
    """
    caller_number = request.POST.get('From', '')

    #  regex check
    expression = r"^\+[1-9]\d{1,14}$"  # E.164 compliant phone numbers
    valid = re.match(expression, caller_number)

    if valid:
        return caller_number
    return None


def get_response_sentiment(sentence):
    """
    Returns True if the given sentence is affirmative
    """
    # Query GPT for intent
    client = OpenAI()
    system_prompt = "Based on the following message, respond if it is AFFIRMATIVE or NEGATIVE."
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": sentence}
        ]
    )
    response_pred = completion.choices[0].message.content

    if response_pred.upper() == "AFFIRMATIVE":
        return True
    return False


@csrf_exempt
def return_main_menu(request):
    """
    Redirects user to main menu based on YES or NO sentiment
    """
    speech_result = request.POST.get('SpeechResult', '').strip().lower()
    declaration = get_response_sentiment(speech_result)
    response = VoiceResponse()

    if declaration:
        response.redirect("/answer/")
    else:
        response.hangup()

    return HttpResponse(str(response), content_type="text/xml")


def appointment_count(request):
    """
    Returns the appointment count of user
    """
    caller_number = get_phone_number(request)
    user = User.objects.get(phone_number=caller_number)
    appointment_count = AppointmentTable.objects.filter(user=user).count()

    return appointment_count


def forward_operator(log=None):
    """
    Relays info to and forwards caller to operator because requested or
    failed strike system
    """
    caller_response = VoiceResponse()

    caller_response.say("I'm transferring you to an operator now. Please hold.")
    if log:
        write_to_log(log,
                    "bot",
                    "I'm transferring you to an operator now. Please hold.")
    dial = Dial()
    dial.number("###-###-####")
    caller_response.append(dial)

    return HttpResponse(str(caller_response), content_type="text/xml")


def write_to_log(log, speaker, message):
    """
    Log conversation as conversation progresses attributing each dialogue
    to a specific party
    """
    if log:
        log.add_transcript(speaker=speaker, message=message)


def send_sms(phone_number_to, message_to_send):
    """
    Send confirmation details via sms to caller
    """
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    try:
        message = client.messages.create(
            body=message_to_send,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number_to)
        return message
    except Exception:
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

    date_final = date_format.replace(f"{date_obj.day}",
                                     f"{date_obj.day}{suffix}")

    return date_final


def get_matching_question(question):
    """
    Takes in a users question and finds the most closely related question,
    returning that question.
    If there are no related questions, none is returned.
    """
    client = OpenAI()

    # Gather all questions to be used in prompt
    questions = FAQ.objects.values_list('question', flat=True)
    questions = [question for question in questions]
    questions.append("Can I speak to an operator?")

    # Set the system prompt to provide instructions on what to do
    system_prompt = f"You are a food pantry assistant with one job. When a user sends you a question, you find the closest match from questions you have memorized and respond with that question. If the question the user asks does not match any of your stored questions, respond with NONE. Only respond with the matching question or NONE.\nYour memorized questions are:{questions}"

    # Make an API call to find the question
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
    )

    # Extract the question from the response
    question_pred = completion.choices[0].message.content
    if question_pred == "NONE":
        return None

    return question_pred


def get_corresponding_answer(question):
    """
    Takes in a predefined question and returns the matching answer.
    If there is no question/answer match in the database, None is returned.
    """
    answer = FAQ.objects.filter(question__iexact=question).first().answer
    return answer


def get_prompted_choice(sentence):
    """
    Takes in a users input and returns the corresponding request.
    Resturns True for ask another question, False for hang up, and None for main menu.
    """
    client = OpenAI()
    # Set the system prompt to provide instructions on what to do
    system_prompt = "Based on the users response, say whether they are most likely asking for the main menu, to ask another question, or to end the call. Respond only with MENU, QUESTION, or END for the corresponding classification."

    # Make an API call to find the question
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": sentence}
        ]
    )

    pred = completion.choices[0].message.content
    if pred.upper() == "QUESTION":
        return True
    elif pred.upper() == "END":
        return False
    else:
        return None


def get_day(speech_result):
    """
    Extracts the day of the week from a given message.
    Only returns the day or NONE.
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
        existing_appointments = AppointmentTable.objects.filter(
            date__date=appointment_date).order_by('start_time')

        # For no appointments that day yet
        if not existing_appointments:
            # TODO: mod by n = fixed appt. length
            number_available_appointments = 4
            return True, appointment_date, number_available_appointments

        current_time = EARLIEST_TIME

        # Check for time slots before appointments until the latest appointment
        for appointment in existing_appointments:
            while current_time < appointment.start_time:
                number_available_appointments += 1
                # Increment by fixed appt time
                current_time = (datetime.combine(datetime.today(),
                                                 current_time) +
                                FIXED_APPT_DURATION).time()
            current_time = appointment.end_time

        # Checks for time slots after last appointment
        # is iterated in the for loop above
        while current_time < LATEST_TIME:
            number_available_appointments += 1
            current_time = (datetime.combine(datetime.today(), current_time) +
                            FIXED_APPT_DURATION).time()

        # If there are available timeslots return True and additional var.
        if number_available_appointments > 0:
            return True, appointment_date, number_available_appointments

    # If no available timeslots for the next month on request day return False
    return False, None, 0


def get_available_times_for_date(appointment_date):
    """
    Retrieve available appointment times for a given date.
    """
    existing_appointments = AppointmentTable.objects.filter(
        date__date=appointment_date).order_by('start_time')
    available_times = []

    current_time = EARLIEST_TIME

    # Adds timeslots between appointments
    for appointment in existing_appointments:
        if current_time < appointment.start_time:
            available_times.append(current_time)
            # Increment by fixed appt time
            current_time = (datetime.combine(datetime.today(), current_time) +
                            FIXED_APPT_DURATION).time()
        current_time = appointment.end_time

    # Adds timeslots after the latest iterated appointment
    while current_time < LATEST_TIME:
        available_times.append(current_time)
        current_time = (datetime.combine(datetime.today(), current_time) +
                        FIXED_APPT_DURATION).time()

    return available_times


def translate_to_language(source_lang, target_lang, text):
    """
    Translate the given text from the given language to the other given language.
    """
    translate_client = translate.Client()

    result = translate_client.translate(text, target_language=target_lang, source_language=source_lang)
    return result["translatedText"]