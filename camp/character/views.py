from django.db import IntegrityError
from django.urls import reverse
from django.views.generic import CreateView
from django.views.generic import DetailView
from rules.contrib.views import AutoPermissionRequiredMixin

from camp.character.models import Character


class CharacterView(AutoPermissionRequiredMixin, DetailView):
    model = Character


class CreateCharacterView(AutoPermissionRequiredMixin, CreateView):
    model = Character
    fields = ["name", "chapter"]

    @property
    def success_url(self):
        if self.object:
            return reverse("character-detail", args=[self.object.id])
        return "/"

    def form_valid(self, form):
        """If the form is valid, save the associated model."""
        self.object = form.save(commit=False)
        self.object.owner = self.request.user
        try:
            self.object.save()
        except IntegrityError:
            return super().form_invalid(form)
        # This has a side effect of creating a primary sheet if one doesn't exist.
        _ = self.object.primary_sheet
        return super().form_valid(form)
