from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def caller_twiml_script(request):
    xml = """
    <Response>
        <Play digits="1" />
        <Pause length="1"/>
        <Say>Hello, my name is Gianpaolo Tabora</Say>
        <Pause length="1"/>
        <Say>Yes</Say>
        <Pause length="1"/>
        <Say>I would like an appointment on Tuesday</Say>
        <Pause length="1"/>
        <Say>10 AM</Say>
        <Pause length="1"/>
        <Say>Yes</Say>
        <Pause length="1"/>
        <Say>I would like to reschedule</Say>
        <Pause length="1"/>
        <Say>Thursday</Say>
        <Pause length="1"/>
        <Say>9:30 AM</Say>
        <Pause length="1"/>
        <Say>Yes</Say>
        <Pause length="1"/>
        <Say>I would like to cancel</Say>
        <Pause length="1"/>
        <Say>Yes</Say>
    </Response>
    """
    return HttpResponse(xml, content_type="text/xml")