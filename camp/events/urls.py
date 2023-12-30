from django.urls import path

from . import views

urlpatterns = [
    path("", views.EventsList.as_view(), name="events-list"),
]
