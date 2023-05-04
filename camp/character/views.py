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
from django.views.generic import DeleteView
from django.views.generic import DetailView
from django.views.generic import ListView
from rules.contrib.views import AutoPermissionRequiredMixin
from rules.contrib.views import objectgetter
from rules.contrib.views import permission_required

from camp.character.models import Character
from camp.character.models import Sheet
from camp.engine.rules.base_engine import BaseFeatureController
from camp.engine.rules.base_engine import CharacterController
from camp.engine.rules.base_models import RankMutation
from camp.engine.rules.tempest.controllers.subfeature_controller import (
    SubfeatureController,
)

from . import forms


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


class DeleteCharacterView(AutoPermissionRequiredMixin, DeleteView):
    model = Character

    def get_success_url(self):
        return reverse("character-list")


@permission_required("character.change_character", fn=objectgetter(Character))
def set_attr(request, pk):
    """Set the character's Level or CP to an arbitrary value."""
    # TODO: Restrict this to either freeplay mode or maybe logistics action.
    character = get_object_or_404(Character, id=pk)
    if request.POST:
        sheet = character.primary_sheet
        controller = sheet.controller
        if "level" in request.POST:
            level = request.POST["level"]
            try:
                level = int(level)
            except ValueError:
                messages.error(request, "Level must be an integer.")
                return redirect("character-detail", pk=pk)
            if controller.xp_level != level:
                controller.xp_level = level
                messages.success(request, f"Level set to {level}.")
        if "cp" in request.POST:
            cp = request.POST["cp"]
            try:
                cp = int(cp)
            except ValueError:
                messages.error(request, "Awarded CP must be an integer.")
                return redirect("character-detail", pk=pk)
            if controller.awarded_cp != cp:
                controller.awarded_cp = cp
                messages.success(request, f"Awarded CP set to {cp}.")

        if d := controller.validate():
            sheet.save()
        else:
            messages.error(request, "Error validating character: %s" % d.reason)
    return redirect("character-detail", pk=pk)


@permission_required("character.change_character", fn=objectgetter(Character))
def feature_view(request, pk, feature_id):
    character = get_object_or_404(Character, id=pk)
    sheet = character.primary_sheet
    controller = sheet.controller
    feature_controller = controller.feature_controller(feature_id)
    currencies: dict[str, str] = {}
    if feature_controller.currency:
        currencies[
            controller.display_name(feature_controller.currency)
        ] = controller.get_prop(feature_controller.currency)
    context = {
        "character": character,
        "controller": controller,
        "feature": feature_controller,
        "currencies": currencies,
        "explain_ranks": feature_controller.explain_ranks(),
    }

    if (rd := feature_controller.can_increase()) or rd.needs_option:
        if request.POST and "purchase" in request.POST:
            pf = forms.FeatureForm(feature_controller, request.POST)
            if pf.is_valid():
                ranks = pf.cleaned_data.get("ranks")
                rm = RankMutation(
                    id=feature_id,
                    option=pf.cleaned_data.get("option"),
                    ranks=int(ranks) if ranks else 1,
                )
                try:
                    result = controller.apply(rm)
                    if result.success:
                        sheet.save()
                        feature_controller = controller.feature_controller(rm.full_id)
                        messages.success(
                            request, f"{feature_controller.display_name()} applied."
                        )
                        return redirect("character-detail", pk=character.id)
                    elif result.reason:
                        messages.error(request, result.reason)
                    else:
                        messages.error(
                            request, "Could not apply purchase for unspecified reasons."
                        )
                except Exception as exc:
                    messages.error(request, "Error applying feature: %s" % exc)
        else:
            pf = forms.FeatureForm(feature_controller)
        context["purchase_form"] = pf
    else:
        context["no_purchase_reason"] = rd.reason

    return render(request, "character/feature_form.html", context)


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
    groups: list[FeatureGroup] = list(by_type.values())
    for group in groups:
        group.taken.sort(key=lambda f: f.display_name())
        group.available.sort(key=lambda f: f.display_name())
    return groups


@dataclasses.dataclass
class FeatureGroup:
    type: str
    name: str
    taken: list[BaseFeatureController] = dataclasses.field(default_factory=list)
    available: list[BaseFeatureController] = dataclasses.field(default_factory=list)
