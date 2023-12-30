from typing import Any

from django.db.models.query import QuerySet
from django.views.generic import ListView

from camp.game.models import Chapter

from . import models


class EventsList(ListView):
    model = models.Event
    ordering = ["chapter", "event_start_date"]

    def get_queryset(self) -> QuerySet[Any]:
        chapters = Chapter.objects.filter(game=self.request.game)
        return super().get_queryset().filter(chapter__in=chapters)
