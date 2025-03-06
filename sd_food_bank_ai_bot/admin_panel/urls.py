"""This module contains URL routing for the web forum application."""

from django.urls import path
from django.shortcuts import redirect
from . import views

urlpatterns = [
    path("", lambda request: redirect('login/'), name="default"),
    path("faqs/", views.admin_panel_faq.faq_page_view, name="faq_page"),
    path("login/", views.admin_panel_faq.login_view, name="login"),
    path("logout/", views.admin_panel_faq.logout_view, name='logout'),
    path("delete_faq/<int:faq_id>/", views.admin_panel_faq.delete_faq, name="delete_faq"),
    path("create_faq/", views.admin_panel_faq.create_faq, name="create_faq"),
    path("edit_faq/<int:faq_id>/", views.admin_panel_faq.edit_faq, name="edit_faq"),
    path("answer/", views.phone_service_faq.answer_call, name="answer_call"),
    path("get_question_from_user/", views.phone_service_faq.get_question_from_user, name="get_question_from_user"),
    path("confirm_question/<str:question>/", views.phone_service_faq.confirm_question, name="confirm_question"),
    path("prompt_question/", views.phone_service_faq.prompt_question, name="prompt_question"),
    path("call_status_update/", views.phone_service_faq.call_status_update, name="call_status_update"),
    path("check_account/", views.check_account, name="check_account"),
    path("confirm_account/", views.confirm_account, name="confirm_account"),
    path("schedule_nearest_available/", views.schedule_nearest_available, name="schedule_nearest_available"),
    path("handle_schedule_response/", views.handle_schedule_response, name="handle_schedule_response"),
    path("handle_schedule_options/", views.handle_schedule_options, name="handle_schedule_options"),
    path("handle_date_input/", views.handle_date_input, name="handle_date_input"),
]
