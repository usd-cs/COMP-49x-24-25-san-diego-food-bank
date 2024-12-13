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
