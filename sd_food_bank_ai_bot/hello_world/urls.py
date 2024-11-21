from django.urls import path
from . import views

urlpatterns = [
    path("", views.hello_page, name="hello_world_page")
]