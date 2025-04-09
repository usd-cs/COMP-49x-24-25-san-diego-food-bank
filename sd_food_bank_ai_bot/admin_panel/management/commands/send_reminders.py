from django.core.management.base import BaseCommand
from django.utils.timezone import now, timedelta
from admin_panel.models import AppointmentTable
from admin_panel.views.utilities import send_sms

class Command(BaseCommand):
    help = 'Sends SMS reminders for appointments 24 hours in advance'

    def handle(self, *args, **kwargs):
        reminder_window_start = now() + timedelta(hours=24)
        reminder_window_end = now() + timedelta(hours=24, minutes=5)

        appointments = AppointmentTable.objects.filter(
            date=reminder_window_start.date(),
            start_time__hour=reminder_window_start.hour,
            start_time__minute__gte=reminder_window_start.minute,
            start_time__minute__lte=reminder_window_end.minute,
        )

        for appt in appointments:
            phone = appt.user.phone_number
            date = appt.date.strftime("%A, %B %d")
            time = appt.start_time.strftime("%I:%M %p")
            message = f"Reminder: You have an appointment scheduled for {date} at {time}."

            try:
                send_sms(phone, message)
                self.stdout.write(self.style.SUCCESS(f"Sent reminder to {phone}"))
            except Exception as e:
                self.stderr.write(f"Failed to send reminder to {phone}: {e}")
