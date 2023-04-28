from __future__ import annotations

import dataclasses
from itertools import chain
from typing import Iterable
from typing import cast

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
from camp.character.models import Sheet
from camp.engine.rules.base_engine import BaseFeatureController
from camp.engine.rules.base_engine import CharacterController
from camp.engine.rules.tempest.controllers.subfeature_controller import (
    SubfeatureController,
)


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
        sheet: Sheet = cast(Sheet, self.object.primary_sheet)
        controller: CharacterController = sheet.controller
        context["sheet"] = sheet
        context["controller"] = controller

        taken_features = controller.list_features(taken=True, available=False)
        available_features = controller.list_features(available=True, taken=False)
        context["feature_groups"] = _features(
            controller, chain(taken_features, available_features)
        )
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
    features = list(
        controller.list_features(type=feature_type, taken=False, available=True)
    )
    currencies_present = {f.currency for f in features if f.currency}
    currencies: dict[str, int] = {}
    for c in currencies_present:
        currencies[controller.display_name(c)] = controller.get_prop(c)
    context = {
        "feature_type_name": controller.display_name(feature_type),
        "character": character,
        "controller": controller,
        "features": features,
        "currencies": currencies,
    }
    return render(request, "character/new_feature.html", context)


def _features(controller, feats: Iterable[BaseFeatureController]) -> list[FeatureGroup]:
    by_type: dict[str, FeatureGroup] = {}
    for feat in feats:
        if isinstance(feat, SubfeatureController):
            # Subfeatures with parents will be rendered with their parents.
            # We should only end up with subfeatures in the list if they are orphaned.
            if feat.parent is not None:
                continue
        if feat.feature_type not in by_type:
            by_type[feat.feature_type] = FeatureGroup(
                type=feat.feature_type, name=controller.display_name(feat.feature_type)
            )
        group = by_type[feat.feature_type]
        if feat.value > 0:
            group.taken.append(feat)
        else:
            group.available.append(feat)
    return list(by_type.values())


@dataclasses.dataclass
class FeatureGroup:
    type: str
    name: str
    taken: list[BaseFeatureController] = dataclasses.field(default_factory=list)
    available: list[BaseFeatureController] = dataclasses.field(default_factory=list)
