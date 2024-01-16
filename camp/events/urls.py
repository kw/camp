from django.urls import path

from . import views

urlpatterns = [
    path("", views.event_list, name="events-list"),
    path("<int:pk>/", views.event_detail, name="event-detail"),
    path("<int:pk>/edit/", views.event_edit, name="event-update"),
    path("<int:pk>/cancel/", views.event_cancel, name="event-cancel"),
    path("<int:pk>/uncancel/", views.event_uncancel, name="event-uncancel"),
    path("new/<slug:slug>/", views.event_create, name="event-create"),
]
