from django.urls import path

from . import views

urlpatterns = [
    # Home / Game Views
    path("", views.HomePageView.as_view(), name="home"),
    path("manage/", views.ManageGameView.as_view(), name="manage-game"),
    # Game Roles
    path("manage/roles/add/", views.CreateGameRoleView.as_view(), name="add-gamerole"),
    path(
        "manage/roles/<str:username>",
        views.UpdateGameRoleView.as_view(),
        name="change-gamerole",
    ),
    path(
        "manage/roles/<str:username>/delete/",
        views.DeleteGameRoleView.as_view(),
        name="delete-gamerole",
    ),
    # Chapter
    path("chapters/<slug:slug>/", views.ChapterView.as_view(), name="chapter-detail"),
    path(
        "chapters/<slug:slug>/manage/",
        views.ChapterManageView.as_view(),
        name="chapter-manage",
    ),
    # Chapter Roles
    path(
        "chapters/<slug:slug>/roles/add",
        views.CreateChapterRoleView.as_view(),
        name="chapterrole-add",
    ),
    path(
        "chapters/<slug:slug>/roles/<str:username>/",
        views.UpdateChapterRoleView.as_view(),
        name="chapterrole-update",
    ),
    path(
        "chapters/<slug:slug>/roles/<str:username>/delete/",
        views.DeleteChapterRoleView.as_view(),
        name="chapterrole-delete",
    ),
    # Ruleset management
    path("manage/rulesets/add/", views.CreateRulesetView.as_view(), name="add-ruleset"),
    path(
        "manage/rulesets/<int:pk>/delete/",
        views.DeleteRulesetView.as_view(),
        name="delete-ruleset",
    ),
]
