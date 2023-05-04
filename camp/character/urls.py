from django.urls import path

from . import views

urlpatterns = [
    # Home / Game Views
    path("", views.CharacterListView.as_view(), name="character-list"),
    path("new/", views.CreateCharacterView.as_view(), name="character-add"),
    path("<int:pk>/", views.CharacterView.as_view(), name="character-detail"),
    path(
        "<int:pk>/delete/", views.DeleteCharacterView.as_view(), name="character-delete"
    ),
    path("<int:pk>/set/", views.set_attr, name="character-set-attr"),
    path(
        "<int:pk>/f/<str:feature_id>/",
        views.feature_view,
        name="character-feature-view",
    ),
]
