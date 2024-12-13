"""This module contains URL routing for the web forum application."""

from django.urls import path
from django.shortcuts import redirect
from . import views

urlpatterns = [
    path("", lambda request: redirect('login/'), name="default"),
    path("faqs/", views.faq_page_view, name="faq_page"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name='logout'),
    path("delete_faq/<int:faq_id>/", views.delete_faq, name="delete_faq"),
    path("create_faq/", views.create_faq, name="create_faq"),
    path("edit_faq/<int:faq_id>/", views.edit_faq, name="edit_faq")
]
