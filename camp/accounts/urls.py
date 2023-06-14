from django.urls import path

from . import views

urlpatterns = [
    path("profile/", views.ProfileDetailView.as_view(), name="account_profile"),
    path("membership/", views.MembershipListView.as_view(), name="membership-list"),
    path(
        "membership-create/",
        views.MembershipCreateView.as_view(),
        name="membership-create",
    ),
    path(
        "membership/<str:pk>/",
        views.MembershipDetailView.as_view(),
        name="membership-detail",
    ),
    path(
        "membership-update/<str:pk>/",
        views.MembershipUpdateView.as_view(),
        name="membership-update",
    ),
    path(
        "membership-delete/<str:pk>/",
        views.MembershipDeleteView.as_view(),
        name="membership-delete",
    ),
]
