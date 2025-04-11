import ssl
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client
import time
import os

class SSLBypassAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = ssl._create_unverified_context()
        return super().init_poolmanager(*args, **kwargs)

# Create a requests Session that ignores SSL verification
session = requests.Session()
session.mount("https://", SSLBypassAdapter())

# Initialize Twilio client with this session
twilio_http_client = TwilioHttpClient(session)
client = Client("NA", "NA", http_client=twilio_http_client)

def run_end_to_end_call():
    ACCOUNT_SID = os.environ.get("TWILIO_SID", "NA")
    AUTH_TOKEN = os.environ.get("TWILIO_AUTH", "NA")

    CALLER_NUMBER = os.environ.get("TWILIO_CALLER", "+18444352594")
    CALLEE_NUMBER = os.environ.get("TWILIO_CALLEE", "+18624292500")
    CALL_URL = "https://joey-champion-reasonably.ngrok-free.app/answer/"

    client = Client(ACCOUNT_SID, AUTH_TOKEN)

    print("📞 Placing call from CALLER_NUMBER to CALLEE_NUMBER...")
    call = client.calls.create(
        to=CALLEE_NUMBER,
        from_=CALLER_NUMBER,
        url=CALL_URL,
        method="POST",
        record=True
    )

    print(f"✅ Call SID: {call.sid}")
    print("🎙️ Call in progress... Waiting for flow to complete...")

    while True:
        call_status = client.calls(call.sid).fetch().status
        print(f"🔄 Call status: {call_status}")
        if call_status in ["completed", "failed", "busy", "no-answer"]:
            break
        time.sleep(5)

    recordings = client.recordings.list(call_sid=call.sid)
    if recordings:
        recording = recordings[0]
        print("📼 Call recorded! Listen here:")
        print(f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}")
    else:
        print("⚠️ No recording found.")

if __name__ == "__main__":
    run_end_to_end_call()
