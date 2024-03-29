from django.urls import path

from . import views

urlpatterns = [
    path("profile/", views.my_profile, name="account_profile"),
    path("profile/edit/", views.profile_edit, name="profile-edit"),
    path("profile/v/<str:username>/", views.profile_view, name="profile-view"),
]
