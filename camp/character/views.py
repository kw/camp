from __future__ import annotations

import dataclasses
from collections import defaultdict
from functools import cached_property
from itertools import chain
from typing import Iterable
from typing import cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.db import transaction
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
from camp.engine.rules.base_models import ChoiceMutation
from camp.engine.rules.base_models import Mutation
from camp.engine.rules.base_models import PropExpression
from camp.engine.rules.base_models import RankMutation
from camp.engine.rules.base_models import dump_mutation
from camp.engine.rules.decision import Decision
from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter

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
        context["undo"] = sheet.last_undo
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


@permission_required(
    "character.change_character", fn=objectgetter(Character), raise_exception=True
)
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


@permission_required(
    "character.change_character", fn=objectgetter(Character), raise_exception=True
)
def feature_view(request, pk, feature_id, anchor=None):
    character = get_object_or_404(Character, id=pk)
    sheet = character.primary_sheet
    controller = cast(TempestCharacter, sheet.controller)
    feature_controller = controller.feature_controller(feature_id)
    currencies: dict[str, str] = {}
    if feature_controller.currency:
        currencies[
            controller.display_name(feature_controller.currency)
        ] = controller.get(feature_controller.currency)

    can_inc = feature_controller.can_increase()
    can_dec = feature_controller.can_decrease()
    pf = None

    if can_inc or can_dec:
        if request.POST and "purchase" in request.POST or "remove" in request.POST:
            success, pf = _try_apply_purchase(
                sheet, feature_id, feature_controller, controller, request
            )
            if success:
                # If we purchased a feature and it has a choice that can be made,
                # stay on the feature page. Otherwise, return to the character page.
                if feature_controller.has_available_choices:
                    return redirect(
                        "character-feature-view", pk=pk, feature_id=feature_id
                    )
                return redirect("character-detail", pk=pk)
        else:
            data = None
            current = feature_controller.value
            next_value = feature_controller.next_value
            if feature_controller.is_concrete:
                # Only use a bound form if this is an existing concrete feature instance.
                data = {"ranks": current if can_dec else next_value}
                if feature_controller.option:
                    data["option"] = feature_controller.option
            pf = forms.FeatureForm(feature_controller, data)

    if request.POST and "choice" in request.POST:
        if "selection" not in request.POST:
            messages.error(request, "No selection made.")
        else:
            mutation = ChoiceMutation(
                id=feature_id,
                choice=request.POST["choice"],
                value=request.POST["selection"],
                remove=request.POST.get("remove", False),
            )
            if result := _apply_mutation(mutation, sheet, controller):
                messages.success(request, result.reason)
            else:
                messages.error(request, result.reason or "Could not apply choice.")

    choices = feature_controller.choices
    context = {
        "character": character,
        "controller": controller,
        "feature": feature_controller,
        "currencies": currencies,
        "explain_ranks": feature_controller.explain(),
        "choices": {k: forms.ChoiceForm(c) for (k, c) in choices.items()}
        if choices
        else {},
        "purchase_form": pf,
    }
    if not can_inc:
        context["no_purchase_reason"] = can_inc.reason
    return render(request, "character/feature_form.html", context)


def _try_apply_purchase(
    sheet: Sheet,
    feature_id: str,
    feature_controller: BaseFeatureController,
    controller: TempestCharacter,
    request,
) -> tuple[bool, forms.FeatureForm]:
    pf = forms.FeatureForm(feature_controller, request.POST)
    if pf.is_valid():
        if request.POST.get("remove"):
            ranks = 0
        else:
            ranks = int(pf.cleaned_data.get("ranks", 1))
        if feature_controller.is_concrete:
            ranks -= feature_controller.value
        if ranks == 0:
            messages.info(request, "No change requested.")
            return True, pf
        expr = PropExpression.parse(feature_id)
        rm = RankMutation(
            id=expr.prop,
            ranks=ranks,
            option=pf.cleaned_data.get("option") or expr.option,
        )
        try:
            if result := _apply_mutation(rm, sheet, controller):
                feature_controller = controller.feature_controller(expr.full_id)
                if ranks > 0:
                    messages.success(
                        request,
                        f"{feature_controller.display_name()} x{ranks} purchased.",
                    )
                elif ranks < 0:
                    messages.warning(
                        request,
                        f"{feature_controller.display_name()} x{abs(ranks)} refunded.",
                    )
                else:
                    messages.info(
                        request, f"{feature_controller.display_name()} applied."
                    )
                return True, pf
            elif result.needs_option:
                messages.error(request, "This feature requires an option.")
            elif result.reason:
                messages.error(request, result.reason)
            else:
                messages.error(
                    request, "Could not apply mutation for unspecified reasons."
                )
        except Exception as exc:
            messages.error(request, f"Error applying mutation: {exc}")
    return False, pf


@permission_required(
    "character.change_character", fn=objectgetter(Character), raise_exception=True
)
def undo_view(request, pk):
    character = get_object_or_404(Character, id=pk)
    sheet = character.primary_sheet
    if request.POST and "undo" in request.POST:
        with transaction.atomic():
            last_undo = sheet.last_undo
            if not last_undo:
                messages.error(request, "Nothing to undo.")
            elif request.POST.get("undo") == str(sheet.last_undo.id):
                mutation = sheet.undo()
                if mutation:
                    description = f"'{sheet.controller.describe_mutation(mutation)}'"
                else:
                    description = "the last action"
                messages.success(request, f"Undid {description}")
                return redirect("character-detail", pk=pk)
    messages.error(request, "Invalid undo request.")
    return redirect("character-detail", pk=pk)


def _features(
    controller: CharacterController, feats: Iterable[BaseFeatureController]
) -> list[FeatureGroup]:
    by_type: dict[str, FeatureGroup] = {}
    for feat in feats:
        if feat.feature_type not in by_type:
            by_type[feat.feature_type] = FeatureGroup(
                type=feat.feature_type,
                name=controller.display_name(feat.feature_type),
                priority=controller.display_priority(feat.feature_type),
            )
        group = by_type[feat.feature_type]
        if feat.is_option_template:
            # Option templates should only appear in the available list,
            # and only if another option is available.
            if feat.can_take_new_option:
                group.add_available(feat)
            # Otherwise, we don't care about them.
        elif feat.value > 0:
            if not feat.internal:
                group.taken.append(feat)
        else:
            group.add_available(feat)
    groups: list[FeatureGroup] = list(t for t in by_type.values() if t)
    for group in groups:
        group.sort()
    groups.sort(key=FeatureGroup.sortkey)
    return groups


@dataclasses.dataclass
class FeatureGroup:
    type: str
    name: str
    taken: list[BaseFeatureController] = dataclasses.field(default_factory=list)
    available: list[BaseFeatureController] = dataclasses.field(default_factory=list)
    available_categories: dict[str, list[BaseFeatureController]] = dataclasses.field(
        default_factory=lambda: defaultdict(list)
    )
    priority: int = 1
    category_priority: dict[str, int] = dataclasses.field(default_factory=dict)

    @property
    def has_available(self) -> bool:
        return self.available or self.available_categories

    def sortkey(self) -> tuple[int, str]:
        return self.priority, self.name

    def __bool__(self) -> bool:
        return bool(self.taken or self.available or self.available_categories)

    def explain(self) -> str | None:
        for feat in self.all():
            return feat.explain_type_group
        return None

    @cached_property
    def explain_list(self) -> list[str]:
        for feat in self.all():
            return feat.explain_list
        return []

    def add_available(self, feat: BaseFeatureController):
        if feat.category:
            self.available_categories[feat.category].append(feat)
            if hasattr(feat, "tier"):
                self.category_priority[feat.category] = feat.tier
        else:
            self.available.append(feat)

    def all(self) -> Iterable[BaseFeatureController]:
        yield from self.taken
        yield from self.available
        for cat in self.available_categories.values():
            yield from cat

    def sort(self):
        # Sort the base taken/available lists by name.
        self.taken.sort(key=lambda f: f.display_name())
        self.available.sort(key=lambda f: f.display_name())
        # Sort the categories themselves
        cats = self.available_categories
        self.available_categories = {k: cats[k] for k in sorted(cats)}
        # Sort the items in each category
        for cat in self.available_categories.values():
            cat.sort(key=lambda f: f.display_name())
        # Sort the categories themselves. This is mostly by name, but a few categories
        # (those that contain tiered abilities) have priority equal to their tier.
        cats = sorted(
            self.available_categories.keys(),
            key=lambda k: (self.category_priority.get(k, 0), k),
        )
        self.available_categories = {k: self.available_categories[k] for k in cats}


def _apply_mutation(
    mutation: Mutation, sheet: Sheet, controller: TempestCharacter
) -> Decision:
    undo_data = controller.dump_dict()
    result = controller.apply(mutation)
    if result:
        with transaction.atomic():
            sheet.save()
            sheet.undo_stack.create(
                mutation=dump_mutation(mutation),
                previous_data=undo_data,
            )
            if len(sheet.undo_stack.all()) > settings.UNDO_STACK_SIZE:
                sheet.undo_stack.order_by("timestamp").first().delete()
            controller.clear_caches()
    return result
