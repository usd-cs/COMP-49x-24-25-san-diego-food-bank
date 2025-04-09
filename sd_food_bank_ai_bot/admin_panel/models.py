from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import datetime, timedelta
from django.utils import timezone


class Admin(AbstractUser):
    """
    Table for storing information on admins
        * approved_for_admin_panel states: 
        - NONE: have not attempted to create account for admin panel access 
        - FALSE: attempted to create account for admin panel access and had matching employee ID and email
                    so waiting for pending approval for account to be officially created
        - TRUE: account creation has been approved so this account has access to admin panel
    """
    foodbank_email = models.EmailField(blank=True, max_length=254, verbose_name="foodbank email")
    foodbank_id = models.CharField(max_length=50, verbose_name="foodbank employee ID", default="unknown")
    approved_for_admin_panel = models.BooleanField(null=True, default=None, verbose_name="approved for admin panel")

class User(models.Model):
    """
    Table for storing user information
    """
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=16)
    email = models.EmailField(unique=True, null=True)


class Tag(models.Model):
    """
    Table for storing tags to assign to FAQs
    """
    name = models.TextField()

    def __str__(self):
        return self.name


class FAQ(models.Model):
    """
    Table for storing FAQs
    """
    question = models.TextField()
    answer = models.TextField()
    tags = models.ManyToManyField(Tag)
    # Automatically update when saving
    updated_at = models.DateTimeField(auto_now=True)


class Log(models.Model):
    """
    Table for storing conversation logs
    """
    phone_number = models.CharField(max_length=15, null=True)
    transcript = models.JSONField(default=list)
    audio = models.FileField(upload_to="conversations/")
    time_started = models.DateTimeField(auto_now_add=True)
    time_ended = models.DateTimeField(default=timezone.now)
    length_of_call = models.DurationField(default=timedelta(seconds=0))
    strikes = models.PositiveIntegerField(default=0)
    intents = models.JSONField(default=dict)

    def add_intent(self, intent):
        """
        Increment count for intent identified during dialogue
        """
        self.intents[intent] = self.intents.get(intent, 0) + 1
        self.save()

    def add_strike(self):
        """Failed intent identification so increment strike count and check
        if forwarding to an operator is necessary"""
        self.strikes += 1
        self.save()
        # Failed intent recognition too many times, forward to operator if
        # this returns True
        return self.strikes >= 2

    def reset_strikes(self):
        """
        Bot progressed to another step in the dialogue so
        reset the strike system
        """
        self.strikes = 0
        self.save()

    def add_transcript(self, speaker, message):
        """
        Append a new message to the call transcript
        """
        self.transcript.append({"speaker": speaker, "message": message})
        self.save()


class AppointmentTable(models.Model):
    """
    Table for storing appointment data
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             null=True, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.TextField()
    date = models.DateTimeField(default=timezone.now)
