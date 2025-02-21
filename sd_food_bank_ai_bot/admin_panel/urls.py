"""This module contains URL routing for the web forum application."""

from django.urls import path
from django.shortcuts import redirect
from . import views
from .views import twilio_webhook, answer_call

urlpatterns = [
    path("", lambda request: redirect('login/'), name="default"),
    path("faqs/", views.faq_page_view, name="faq_page"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name='logout'),
    path("delete_faq/<int:faq_id>/", views.delete_faq, name="delete_faq"),
    path("create_faq/", views.create_faq, name="create_faq"),
    path("edit_faq/<int:faq_id>/", views.edit_faq, name="edit_faq"),
    path("answer/", views.answer_call, name="answer_call"),
    path("twilio_webhook/", views.twilio_webhook, name="twilio_webhook"),
    path("text_to_speech/", views.text_to_speech, name="text_to_speech"),
    path("get_question_from_user/", views.get_question_from_user, name="get_question_from_user"),
    path("confirm_question/<str:question>/", views.confirm_question, name="confirm_question"),
    path("call_status_update/", views.call_status_update, name="call_status_update")
]
