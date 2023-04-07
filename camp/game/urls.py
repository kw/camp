from django.urls import path

from . import views

urlpatterns = [
    # Home / Game Views
    path("", views.HomePageView.as_view(), name="home"),
    path("manage/", views.ManageGameView.as_view(), name="game-manage"),
    # Game Roles
    path("manage/roles/new/", views.CreateGameRoleView.as_view(), name="gamerole-add"),
    path(
        "manage/roles/<str:username>",
        views.UpdateGameRoleView.as_view(),
        name="gamerole-update",
    ),
    path(
        "manage/roles/<str:username>/delete/",
        views.DeleteGameRoleView.as_view(),
        name="gamerole-delete",
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
        "chapters/<slug:slug>/roles/new",
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
    path("manage/rulesets/new/", views.CreateRulesetView.as_view(), name="ruleset-add"),
    path(
        "manage/rulesets/<int:pk>/edit/",
        views.UpdateRulesetView.as_view(),
        name="ruleset-update",
    ),
    path(
        "manage/rulesets/<int:pk>/delete/",
        views.DeleteRulesetView.as_view(),
        name="ruleset-delete",
    ),
]
