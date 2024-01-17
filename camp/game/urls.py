from django.urls import path

from .views import events
from .views import game

urlpatterns = [
    # Home / Game Views
    path("", game.HomePageView.as_view(), name="home"),
    path("manage/", game.ManageGameView.as_view(), name="game-manage"),
    # Game Roles
    path("manage/roles/new/", game.CreateGameRoleView.as_view(), name="gamerole-add"),
    path(
        "manage/roles/<str:username>",
        game.UpdateGameRoleView.as_view(),
        name="gamerole-update",
    ),
    path(
        "manage/roles/<str:username>/delete/",
        game.DeleteGameRoleView.as_view(),
        name="gamerole-delete",
    ),
    # Chapter
    path("chapters/<slug:slug>/", game.ChapterView.as_view(), name="chapter-detail"),
    path(
        "chapters/<slug:slug>/manage/",
        game.ChapterManageView.as_view(),
        name="chapter-manage",
    ),
    # Chapter Roles
    path(
        "chapters/<slug:slug>/roles/new",
        game.CreateChapterRoleView.as_view(),
        name="chapterrole-add",
    ),
    path(
        "chapters/<slug:slug>/roles/<str:username>/",
        game.UpdateChapterRoleView.as_view(),
        name="chapterrole-update",
    ),
    path(
        "chapters/<slug:slug>/roles/<str:username>/delete/",
        game.DeleteChapterRoleView.as_view(),
        name="chapterrole-delete",
    ),
    # Ruleset management
    path("manage/rulesets/new/", game.CreateRulesetView.as_view(), name="ruleset-add"),
    path(
        "manage/rulesets/<int:pk>/edit/",
        game.UpdateRulesetView.as_view(),
        name="ruleset-update",
    ),
    path(
        "manage/rulesets/<int:pk>/delete/",
        game.DeleteRulesetView.as_view(),
        name="ruleset-delete",
    ),
    # Campaign management
    path("campaigns/new/", game.CreateCampaignView.as_view(), name="campaign-add"),
    path("campaigns/<slug:slug>/", game.CampaignView.as_view(), name="campaign-detail"),
    path(
        "campaigns/<slug:slug>/update/",
        game.UpdateCampaignView.as_view(),
        name="campaign-update",
    ),
    path(
        "campaigns/<slug:slug>/delete/",
        game.DeleteCampaignView.as_view(),
        name="campaign-delete",
    ),
    # Events
    path("events/", events.event_list, name="events-list"),
    path("events/<int:pk>/", events.event_detail, name="event-detail"),
    path("events/<int:pk>/edit/", events.event_edit, name="event-update"),
    path("events/<int:pk>/cancel/", events.event_cancel, name="event-cancel"),
    path("events/<int:pk>/uncancel/", events.event_uncancel, name="event-uncancel"),
    path("events/new/<slug:slug>/", events.event_create, name="event-create"),
]
