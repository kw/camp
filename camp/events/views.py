from django.views.generic import CreateView
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import UpdateView
from django.views.generic.edit import FormMixin

from camp.game.models import Chapter

from . import forms
from . import models


class EventsList(ListView):
    model = models.Event
    ordering = ["chapter", "event_start_date"]

    def get_queryset(self):
        chapters = Chapter.objects.filter(game=self.request.game)
        return super().get_queryset().filter(chapter__in=chapters)


class EventDetail(DetailView):
    model = models.Event

    def get_queryset(self):
        return super().get_queryset().prefetch_related("campaign", "chapter")


class EventCreate(CreateView):
    model = models.Event
    form_class = forms.EventCreateForm

    def form_valid(self, form):
        # We want to capture the user performing the create.
        # To do this, we need to skip the superclass (ModelFormMixin)
        # method entirely, since it also populates self.object from
        # the form and saves it.
        self.object = form.save(commit=False)
        self.object.creator = self.request.user
        self.object.save()
        form.save_m2m()
        return FormMixin.form_valid(self, form)


class EventUpdate(UpdateView):
    model = models.Event
    form_class = forms.EventUpdateForm

    def get_queryset(self):
        return super().get_queryset().prefetch_related("campaign", "chapter")
