"""This module contains URL routing for the web forum application."""

from django.urls import path
from django.shortcuts import redirect
from . import views

urlpatterns = [
    # Utilities
    path("return_main_menu/", views.return_main_menu, name="return_main_menu"),
    
    # Admin Panel FAQ
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
   
   # Phone Service Schedule
    path("check_account/", views.check_account, name="check_account"),
    path("confirm_account/", views.confirm_account, name="confirm_account"),
    path("get_name/", views.phone_service_schedule.get_name, name="get_name"),
    path("process_name_confirmation/<str:name_encoded>/", views.phone_service_schedule.process_name_confirmation, name="process_name_confirmation"),
    path("request_date_availability/", views.request_date_availability, name="request_date_availability"),
    path("confirm_request_date_availability/", views.confirm_request_date_availability, name="confirm_request_date_availability"),
    path("confirm_available_date/", views.confirm_available_date, name="confirm_available_date"),
    path("check_for_appointment/", views.check_for_appointment, name="check_for_appointment"),
    path("request_preferred_time_under_four/", views.request_preferred_time_under_four, name="request_preferred_time_under_four"),
    path("request_preferred_time_over_three/", views.request_preferred_time_over_three, name="request_preferred_time_over_three"),
    path("generate_requested_time/", views.generate_requested_time, name="generate_requested_time"),
    path("find_requested_time/<str:time_encoded>/", views.find_requested_time, name="find_requested_time"),
    path("suggested_time_response/<str:time_encoded>/<str:date>/", views.suggested_time_response, name="suggested_time_response"),
    path("get_time_response/", views.get_time_response, name="get_time_response"),
    path("given_time_response/<str:time_encoded>/<str:date>/", views.given_time_response, name="given_time_response"),
    path("confirm_time_selection/<str:time_encoded>/<str:date>/", views.confirm_time_selection, name="confirm_time_selection"),
    path("final_confirmation/<str:time_encoded>/<str:date>/", views.final_confirmation, name="final_confirmation"),

    # Phone service cancellation
    path("cancel_appointment/<int:appointment_id>/", views.cancel_appointment, name="cancel_appointment"),
    path("no_account_reroute/", views.no_account_reroute, name="no_account_reroute"),
    path("reroute_caller_with_no_account/", views.reroute_caller_with_no_account, name="reroute_caller_with_no_account"),
    path("cancel_initial_routing/", views.cancel_initial_routing, name="cancel_initial_routing"),

    # Phone Service Reschedule
    path("no_account_reroute/", views.no_account_reroute, name="no_account_reroute"),
    path("reroute_caller_with_no_account/", views.reroute_caller_with_no_account, name="reroute_caller_with_no_account"),
    path("prompt_reschedule_appointment_over_one", views.prompt_reschedule_appointment_over_one, name="prompt_reschedule_appointment_over_one"),
    path("prompt_reschedule_appointment_one", views.prompt_reschedule_appointment_one, name="prompt_reschedule_appointment_one"),
    path("generate_requested_date", views.generate_requested_date, name="generate_requested_date"),
    path("confirm_requested_date/<str:date_encoded>/", views.confirm_requested_date, name="confirm_requested_date"),
]