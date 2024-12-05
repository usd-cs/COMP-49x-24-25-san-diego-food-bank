"""This module contains URL routing for the web forum application."""

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

# <int:post_id>/
urlpatterns = [
path("", views.home_view, name="home"),
path("post/", views.post_view, name="post"),
path("create_post/", views.create_post_view, name="create post"),
path("login/", views.login_view, name="login"),
path("logout/", auth_views.LogoutView.as_view(), name="logout"),
path('reply/<int:post_id>/', views.reply_view, name='reply'),
path('delete/<int:post_id>/', views.delete_post_view, name="delete"),
path('delete_comment/<int:comment_id>/', views.delete_comment_view, name="delete comment")
]
