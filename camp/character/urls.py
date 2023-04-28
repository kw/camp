from django.urls import path

from . import views

urlpatterns = [
    # Home / Game Views
    path("", views.CharacterListView.as_view(), name="character-list"),
    path("new/", views.CreateCharacterView.as_view(), name="character-add"),
    path("<int:pk>/", views.CharacterView.as_view(), name="character-detail"),
    path("<int:pk>/set/", views.set_attr, name="character-set-attr"),
    path(
        "<int:pk>/new/<str:feature_type>/",
        views.new_feature,
        name="character-new-feature",
    ),
]
