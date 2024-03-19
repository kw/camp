from django.urls import path
from django.urls import register_converter

from . import views


class FeatureIdEncoder:
    regex = r"[\w&.․$()!?➡：;,<>[\]|%@\\ +-]+"

    def to_python(self, value):
        return value.replace("$", "/")

    def to_url(self, value):
        return value.replace("/", "$")


register_converter(FeatureIdEncoder, "feature")


urlpatterns = [
    # Home / Game Views
    path("", views.CharacterListView.as_view(), name="character-list"),
    path("new/", views.CreateCharacterView.as_view(), name="character-add"),
    path("<int:pk>/", views.CharacterView.as_view(), name="character-detail"),
    path("<int:pk>/delete/", views.delete_character, name="character-delete"),
    path("<int:pk>/set/", views.set_attr, name="character-set-attr"),
    path("<int:pk>/name/", views.set_name, name="character-set-name"),
    path("<int:pk>/undo/", views.undo_view, name="character-undo"),
    path(
        "<int:pk>/f/<feature:feature_id>/",
        views.feature_view,
        name="character-feature-view",
    ),
]
