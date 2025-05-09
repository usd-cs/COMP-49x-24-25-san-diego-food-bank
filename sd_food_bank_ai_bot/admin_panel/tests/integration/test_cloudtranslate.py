# Integration test between cloud translate and FAQ process

import pytest
from django.test import Client
from admin_panel.models import User, Log
from google.cloud import translate_v2 as translate


@pytest.mark.django_db
def test_google_translate_and_manual_faq_log():
    client = Client()
    test_phone = "+19999999999"
    spanish_input = "¿Dónde están ubicados?"

    translator = translate.Client()
    translated = translator.translate(spanish_input, source_language="es", target_language="en")
    translated_question = translated["translatedText"]

    # Basic check on translation result
    assert "where" in translated_question.lower()

    User.objects.create(phone_number=test_phone, language="es")
    log = Log.objects.create(phone_number=test_phone, language="es")

    log.intents = {
        "faq": {
            translated_question: 1
        }
    }
    log.save()

    log.refresh_from_db()
    assert "faq" in log.intents
    assert translated_question in log.intents["faq"]
    assert log.intents["faq"][translated_question] == 1
