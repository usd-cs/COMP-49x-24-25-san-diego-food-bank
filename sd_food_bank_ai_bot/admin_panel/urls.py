"""This module contains URL routing for the web forum application."""

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("faqs/", views.faq_page_view, name="faq_page"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name='logout'),
    path("delete_faq/<int:faq_id>/", views.delete_faq, name="delete_faq"),
]
