from django.db import models
from django.contrib.auth.models import AbstractUser


class Admin(AbstractUser):
    """Table for storing information on admins"""


class Tag(models.Model):
    """Table for storing tags to assign to FAQs"""
    name = models.TextField()

    def __str__(self):
        return self.name


class FAQ(models.Model):
    """Table for storing FAQs"""
    question = models.TextField()
    answer = models.TextField()
    tags = models.ManyToManyField(Tag)
    updated_at = models.DateTimeField(auto_now=True)  # Automatically update when saving

class Log(models.Model):
    """Table for storing conversation logs"""
    phone_number = models.CharField(max_length = 15)
    transcript = models.JSONField(default = list)
    audio = models.FileField(upload_to = "conversations/")
    time_started = models.DateTimeField(auto_now_add = True)
    time_ended = models.DateTimeField()
    length_of_call = models.DurationField()
    strikes = models.PositiveIntegerField(default = 0)
    intents = models.JSONField(default = dict)

    def add_intent(self, intent):
        """Increment count for intent identified during dialogue"""
        self.intents[intent] = self.intents.get(intent, 0) + 1
        self.save()
    
    def add_strike(self):
        """Failed intent identification so increment strike count and check
        if forwarding to an operator is necessary"""
        self.strikes += 1
        self.save()
        return self.strikes >= 2 # Failed intent recognition too many times, forward to operator if this returns True
    
    def add_transcript(self, speaker, message):
        """Append a new message to the call transcript"""
        self.transcript.append({"speaker": speaker, "message": message})
        self.save()