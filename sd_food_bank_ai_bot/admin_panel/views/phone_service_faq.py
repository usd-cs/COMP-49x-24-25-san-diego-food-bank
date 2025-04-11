from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ..models import Log
from django.http import HttpResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
import urllib.parse
from django.utils import timezone
from .utilities import (strike_system_handler, forward_operator, write_to_log,
                        get_response_sentiment,
                        get_matching_question, get_corresponding_answer)
from .phone_service_schedule import CALLER, BOT
from .utilities import get_phone_number
from ..models import User


TIMEOUT_LENGTH = 4  # The length of time the bot waits for a response


@csrf_exempt
def answer_call(request):
    """
    Brief greeting upon answering incoming phone calls and prompt menu options.
    """
    phone_number = request.POST.get('From')
    log = Log.objects.create(phone_number=phone_number)
    caller_response = VoiceResponse()

    phone_number = get_phone_number(request)

    if phone_number:
        user, created = User.objects.get_or_create(
            phone_number=phone_number,
            defaults={
                "first_name": "NaN",
                "last_name": "NaN",
            }
        )

        digit_input = request.POST.get('Digits', '')
        if digit_input:
            if digit_input == "0":
                if user.language == "en":
                    user.language = "es"
                else:
                    user.language = "en"
                user.save()
                caller_response.redirect("/answer/")
            elif digit_input == "1":
                caller_response.redirect("/check_account/?action=schedule")
            elif digit_input == "2":  # Reschedule
                caller_response.redirect("/check_account/?action=reschedule")
            elif digit_input == "3":  # Cancel
                caller_response.redirect("/check_account/?action=cancel")
            elif digit_input == "4":  # FAQs
                caller_response.redirect("/prompt_question/")
            elif digit_input == "5":
                forward_operator(log)
            else:
                caller_response.say("Please choose a valid option.")

        gather = Gather(num_digits=1)

        if user.language == "en":
            gather.say("Thank you for calling the San Diego Food Bank!", language="en")
            write_to_log(log, BOT, "Thank you for calling the San Diego Food Bank!")
            gather.say("Para español presione 0.", language="es")
            write_to_log(log, BOT, "Para español presione 0.")
            gather.say("press 1 to schedule an appointment, press 2 to reschedule an appointment,\
                        press 3 to cancel an appointment, press 4 to ask about specific inquiries,\
                        or press 5 to be forwarded to an operator.", language="en")
            write_to_log(log, BOT, "press 1 to schedule an appointment, press 2 to reschedule an appointment,\
                        press 3 to cancel an appointment, press 4 to ask about specific inquiries,\
                        or press 5 to be forwarded to an operator.")
        else:
            gather.say("Gracias por llamar al banco de alimentos de San Diego!", language="es")
            write_to_log(log, BOT, "Gracias por llamar al banco de alimentos de San Diego!")
            gather.say("For english press 0.", language="en")
            write_to_log(log, BOT, "For english press 0.")
            gather.say("presione 1 para programar una cita, presione 2 para reprogramar una cita, presione\
                        3 para cancelar una cita, presione 4 para preguntar sobre consultas específicas\
                        o presione 5 para ser remitido a un operador.", language="es")
            write_to_log(log, BOT, "presione 1 para programar una cita, presione 2 para reprogramar una cita, presione\
                        3 para cancelar una cita, presione 4 para preguntar sobre consultas específicas\
                        o presione 5 para ser remitido a un operador.")
    
        caller_response.append(gather)
        
        # If no input, repeat process
        caller_response.redirect("/answer/")
    else:
        caller_response.say("Sorry, we are unable to help you at this time.")
        write_to_log(log, BOT,
                     "Sorry, we are unable to help you at this time.")
        forward_operator(log)

    return HttpResponse(str(caller_response), content_type='text/xml')


@csrf_exempt
def call_status_update(request):
    """
    Looks at call status from twilio webhook and stores call status data
    when receiving a POST request.
    """
    if request.method == 'POST':
        call_status = request.POST.get('CallStatus')
        phone_number = request.POST.get('From')

        if call_status == 'completed':
            log = Log.objects.filter(phone_number=phone_number).last()
            if log:
                log.time_ended = timezone.now()

                if log.time_started:
                    call_duration = log.time_ended - log.time_started
                    log.length_of_call = call_duration

                log.save()

        return JsonResponse({"status": "success"})

    else:
        return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def prompt_question(request):
    """
    Used to prompt the user for a question. Main use is to loop
    till end of call.
    """
    phone_number = request.POST.get('From')
    log = Log.objects.filter(phone_number=phone_number).last()
    caller_response = VoiceResponse()
    gather = Gather(input="speech", timeout=TIMEOUT_LENGTH,
                    action="/get_question_from_user/")
    gather.say("What can I help you with?")
    write_to_log(log, BOT, "What can I help you with?")
    caller_response.append(gather)

    return HttpResponse(str(caller_response), content_type='text/xml')


@csrf_exempt
def get_question_from_user(request):
    """
    Gets the users question and interprets it
    """
    speech_result = request.POST.get('SpeechResult', '')
    phone_number = request.POST.get('From')
    log = Log.objects.filter(phone_number=phone_number).last()
    write_to_log(log, CALLER, speech_result)
    caller_response = VoiceResponse()
    if speech_result:
        question = get_matching_question(speech_result)
        if question:
            question_encoded = urllib.parse.quote(question)
            gather = Gather(input="speech", timeout=TIMEOUT_LENGTH,
                            action=f"/confirm_question/{question_encoded}/")
            gather.say(f"You asked: {question} Is this correct?")
            write_to_log(log, BOT, f"You asked: {question} Is this correct?")
            caller_response.append(gather)
        else:  # No matching question found
            # Add a strike
            strike_system_handler(log)
            caller_response.say("Sorry, I don't have the answer to that at this time. Maybe try rephrasing your question.")
            write_to_log(log, BOT, "Sorry, I don't have the answer to that at this time. Maybe try rephrasing your question.")
            caller_response.redirect("/prompt_question/")
    else:
        caller_response.say("Sorry, I couldn't understand that.")
        write_to_log(log, BOT, "Sorry, I couldn't understand that.")

    return HttpResponse(str(caller_response), content_type='text/xml')


@csrf_exempt
def confirm_question(request, question):
    """
    Confirms the users question is correct and provides the answer
    """
    speech_result = request.POST.get('SpeechResult', '')
    phone_number = request.POST.get('From')
    log = Log.objects.filter(phone_number=phone_number).last()
    caller_response = VoiceResponse()
    write_to_log(log, CALLER, speech_result)

    if speech_result:
        sentiment = get_response_sentiment(speech_result)
        if sentiment:
            question = urllib.parse.unquote(question)

            if "operator" in question:
                return forward_operator(log)

            answer = get_corresponding_answer(question)

            caller_response.say(answer)
            write_to_log(log, BOT, answer)

            caller_response.redirect("/prompt_question/")
        # If caller has indicated unsatisfactory response, add a string
        # and retry
        else:
            # Add a strike
            strike_system_handler(log)
            caller_response.say("Sorry about that. Please try asking again or rephrasing.")
            write_to_log(log, BOT, "Sorry about that. Please try asking again or rephrasing.")
            caller_response.redirect("/prompt_question/")
    else:
        caller_response.say("Sorry, I couldn't understand that. Please try again.")
        write_to_log(log, BOT, "Sorry, I couldn't understand that. Please try again.")
        caller_response.redirect("/prompt_question/")

    return HttpResponse(str(caller_response), content_type='text/xml')
