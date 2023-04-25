from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import CreateView
from django.views.generic import DetailView
from django.views.generic import ListView
from rules.contrib.views import AutoPermissionRequiredMixin

from camp.character.models import Character


class CharacterListView(LoginRequiredMixin, ListView):
    model = Character

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return self.model.objects.filter(owner=self.request.user)
        return self.model.objects.none()


class CharacterView(AutoPermissionRequiredMixin, DetailView):
    model = Character

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        # Some day, when we support multiple sheets, this will need to be smarter.
        context["sheet"] = sheet = self.object.primary_sheet
        context["controller"] = controller = sheet.controller
        controller
        return context


class CreateCharacterView(AutoPermissionRequiredMixin, CreateView):
    model = Character
    fields = ["name"]

    @property
    def success_url(self):
        if self.object:
            return reverse("character-detail", args=[self.object.id])
        return "/"

    def form_valid(self, form):
        """If the form is valid, save the associated model."""
        self.object = form.save(commit=False)
        self.object.owner = self.request.user
        self.object.game = self.request.game
        try:
            self.object.save()
        except IntegrityError:
            return super().form_invalid(form)
        # This has a side effect of creating a primary sheet if one doesn't exist.
        _ = self.object.primary_sheet
        return super().form_valid(form)


def new_feature(request, id, feature_type):
    character = get_object_or_404(Character, id=id)
    sheet = character.primary_sheet
    controller = sheet.controller

    if "feature" in request.POST:
        feature = request.POST["feature"]
        try:
            controller.apply(feature)
            sheet.save()
            messages.success(request, f"{feature} applied.")
            return redirect("character-detail", pk=id)
        except Exception as exc:
            messages.error(request, "Error applying feature: %s" % exc)
    context = {
        "feature_type_name": controller.display_name(feature_type),
        "character": character,
        "controller": controller,
        "features": controller.list_features(
            type=feature_type, taken=False, available=True
        ),
    }
    return render(request, "character/new_feature.html", context)
