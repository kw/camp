from django.urls import path

from .views import event_views
from .views import game_views

urlpatterns = [
    # Home / Game Views
    path("", game_views.home_view, name="home"),
    path("manage/", game_views.ManageGameView.as_view(), name="game-manage"),
    # Game Roles
    path(
        "manage/roles/new/",
        game_views.CreateGameRoleView.as_view(),
        name="gamerole-add",
    ),
    path(
        "manage/roles/<str:username>",
        game_views.UpdateGameRoleView.as_view(),
        name="gamerole-update",
    ),
    path(
        "manage/roles/<str:username>/delete/",
        game_views.DeleteGameRoleView.as_view(),
        name="gamerole-delete",
    ),
    # Chapter
    path(
        "chapters/<slug:slug>/", game_views.ChapterView.as_view(), name="chapter-detail"
    ),
    path(
        "chapters/<slug:slug>/manage/",
        game_views.ChapterManageView.as_view(),
        name="chapter-manage",
    ),
    # Chapter Roles
    path(
        "chapters/<slug:slug>/roles/new",
        game_views.CreateChapterRoleView.as_view(),
        name="chapterrole-add",
    ),
    path(
        "chapters/<slug:slug>/roles/<str:username>/",
        game_views.UpdateChapterRoleView.as_view(),
        name="chapterrole-update",
    ),
    path(
        "chapters/<slug:slug>/roles/<str:username>/delete/",
        game_views.DeleteChapterRoleView.as_view(),
        name="chapterrole-delete",
    ),
    # Ruleset management
    path(
        "manage/rulesets/new/",
        game_views.CreateRulesetView.as_view(),
        name="ruleset-add",
    ),
    path(
        "manage/rulesets/<int:pk>/edit/",
        game_views.UpdateRulesetView.as_view(),
        name="ruleset-update",
    ),
    path(
        "manage/rulesets/<int:pk>/delete/",
        game_views.DeleteRulesetView.as_view(),
        name="ruleset-delete",
    ),
    path(
        "manage/rulesets/<int:pk>/fetch/",
        game_views.fetch_ruleset_view,
        name="fetch-ruleset",
    ),
    # Campaign management
    path(
        "campaigns/new/", game_views.CreateCampaignView.as_view(), name="campaign-add"
    ),
    path(
        "campaigns/<slug:slug>/",
        game_views.CampaignView.as_view(),
        name="campaign-detail",
    ),
    path(
        "campaigns/<slug:slug>/update/",
        game_views.UpdateCampaignView.as_view(),
        name="campaign-update",
    ),
    path(
        "campaigns/<slug:slug>/delete/",
        game_views.DeleteCampaignView.as_view(),
        name="campaign-delete",
    ),
    path(
        "campaigns/<slug:slug>/myawards/",
        game_views.myawards_view,
        name="myawards",
    ),
    path(
        "campaigns/<slug:slug>/awards/grant/",
        game_views.grant_award,
        name="grant-award",
    ),
    # Events
    path("events/", event_views.event_list, name="events-list"),
    path("events/<int:pk>/", event_views.event_detail, name="event-detail"),
    path("events/<int:pk>/edit/", event_views.event_edit, name="event-update"),
    path("events/<int:pk>/cancel/", event_views.event_cancel, name="event-cancel"),
    path(
        "events/<int:pk>/uncancel/", event_views.event_uncancel, name="event-uncancel"
    ),
    path("events/new/<slug:slug>/", event_views.event_create, name="event-create"),
    path(
        "events/<int:pk>/register/",
        event_views.register_view,
        name="event-register",
    ),
    path(
        "events/<int:pk>/unregister/",
        event_views.unregister_view,
        name="event-unregister",
    ),
    path(
        "events/<int:pk>/registrations/",
        event_views.list_registrations,
        name="registration-list",
    ),
    path(
        "events/<int:pk>/registrations/<str:username>/",
        event_views.view_registration,
        name="registration-view",
    ),
    path(
        "events/<int:pk>/complete/",
        event_views.mark_event_complete,
        name="event-complete",
    ),
    # Event reports
    path(
        "events/<int:pk>/reports/<str:report_type>/",
        event_views.trigger_event_report,
        name="trigger-event-report",
    ),
    path(
        "events/<int:pk>/reports/<str:report_type>/poll/",
        event_views.poll_event_report,
        name="poll-event-report",
    ),
    path(
        "events/<int:pk>/reports/<str:report_type>/download/",
        event_views.download_event_report,
        name="download-event-report",
    ),
]
