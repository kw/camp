from django.urls import path

from . import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home"),
    path("manage/", views.ManageGameView.as_view(), name="manage-game"),
    path("manage/roles/add/", views.CreateGameRoleView.as_view(), name="add-gamerole"),
    path(
        "manage/roles/<str:username>/update/",
        views.UpdateGameRoleView.as_view(),
        name="change-gamerole",
    ),
    path(
        "manage/roles/<str:username>/delete/",
        views.DeleteGameRoleView.as_view(),
        name="delete-gamerole",
    ),
]
