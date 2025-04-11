import time
from twilio.rest import Client

# Replace with your real values
ACCOUNT_SID = "YOUR_ACCOUNT_SID"
AUTH_TOKEN = "YOUR_AUTH_TOKEN"

CALLER_NUMBER = "+1XXXXXXXXXX"  # Your Twilio number making the call
CALLEE_NUMBER = "+1YYYYYYYYYY"  # Your Django-exposed Twilio number (linked to /answer/)
CALL_URL = "https://sd-food-bank.dedyn.io/answer/"  # This should point to /answer/

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# STEP 1: Place call from caller to callee (which is linked to /answer/)
print("📞 Placing call from CALLER_NUMBER to CALLEE_NUMBER...")
call = client.calls.create(
    to=CALLEE_NUMBER,
    from_=CALLER_NUMBER,
    url=CALL_URL,  # This URL must return TwiML
    method="POST",
    record=True  # ✅ Record the call for demo purposes
)

print(f"✅ Call SID: {call.sid}")
print("🎙️ Call in progress... Waiting for flow to complete...")

# STEP 2: Poll call until it finishes
while True:
    call_status = client.calls(call.sid).fetch().status
    print(f"🔄 Call status: {call_status}")
    if call_status in ["completed", "failed", "busy", "no-answer"]:
        break
    time.sleep(5)

# STEP 3: Retrieve recording
recordings = client.recordings.list(call_sid=call.sid)
if recordings:
    recording = recordings[0]
    print(f"📼 Call recorded! Access recording here:")
    print(f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}")
else:
    print("⚠️ No recording found.")
