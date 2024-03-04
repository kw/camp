from allauth.account.models import EmailAddress
from django import http
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.urls import reverse_lazy
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView
from django.views.generic import DeleteView
from django.views.generic import DetailView
from django.views.generic import UpdateView
from rules.contrib.views import AutoPermissionRequiredMixin
from rules.contrib.views import permission_required

from camp.accounts.models import Membership
from camp.character.models import Character
from camp.engine.rules.base_engine import Engine
from camp.engine.rules.tempest.records import AwardCategory

from .. import forms
from ..models import Award
from ..models import Campaign
from ..models import Chapter
from ..models import ChapterRole
from ..models import Event
from ..models import Game
from ..models import GameRole
from ..models import PlayerCampaignData
from ..models import Ruleset


def _get_game(request, *args, **kwargs):
    return request.game


@require_GET
def home_view(request):
    game = request.game
    context = {"game": game, "open_campaigns": game.campaigns.filter(is_open=True)}

    if request.user.is_authenticated:
        context["character_list"] = Character.objects.filter(
            owner=request.user,
            discarded_date=None,
        ).order_by("-campaign", "name")
        claimable, unclaimable = Award.unclaimed_for(request.user)
        context["claimable_awards"] = claimable.all()
        context["unclaimable_award_count"] = unclaimable.count()
        context["unclaimable_award_emails"] = sorted(
            {a.email.lower() for a in unclaimable}
        )

    return render(request, "game/game_home.html", context)


class ManageGameView(AutoPermissionRequiredMixin, UpdateView):
    model = Game
    fields = ["name", "description", "is_open"]
    success_url = "/"

    def get_object(self):
        return self.request.game


class ChapterView(DetailView):
    model = Chapter


class ChapterManageView(AutoPermissionRequiredMixin, UpdateView):
    model = Chapter
    fields = ["name", "description", "is_open"]
    template_name_suffix = "_manage"

    @property
    def success_url(self):
        if self.object:
            return reverse("chapter-detail", args=[self.object.slug])
        return "/"


class CreateChapterRoleView(AutoPermissionRequiredMixin, CreateView):
    model = ChapterRole

    fields = [
        "user",
        "title",
        "manager",
        "logistics_staff",
        "plot_staff",
        "tavern_staff",
    ]

    @property
    def success_url(self):
        if self.object:
            return reverse("chapter-manage", args=[self.object.chapter.slug])
        return "/"

    @property
    def chapter(self):
        chapter_slug = self.kwargs.get("slug")
        return get_object_or_404(Chapter, slug=chapter_slug)

    def get_permission_object(self):
        return self.chapter

    def form_valid(self, form):
        """If the form is valid, save the associated model."""
        # You don't get to choose which Game the role applies to.
        # Intercept the model to set the Game manually before saving.
        self.object = form.save(commit=False)
        self.object.chapter = self.chapter
        try:
            self.object.save()
        except IntegrityError:
            form.add_error("user", "User already has a role for this game.")
            return super().form_invalid(form)
        return super().form_valid(form)


class UpdateChapterRoleView(AutoPermissionRequiredMixin, UpdateView):
    model = ChapterRole
    fields = ["title", "manager", "logistics_staff", "plot_staff", "tavern_staff"]

    @property
    def chapter(self):
        chapter_slug = self.kwargs.get("slug")
        return get_object_or_404(Chapter, slug=chapter_slug)

    @property
    def success_url(self):
        if self.object:
            return reverse("chapter-manage", args=[self.object.chapter.slug])
        return "/"

    def get_object(self):
        queryset = self.get_queryset()
        username = self.kwargs.get("username")
        try:
            return queryset.filter(user__username=username, chapter=self.chapter).get()
        except queryset.model.DoesNotExist:
            raise Http404("No ChapterRole found matching the query")


class DeleteChapterRoleView(AutoPermissionRequiredMixin, DeleteView):
    model = ChapterRole
    queryset = ChapterRole.objects.select_related("user", "chapter")

    @property
    def chapter(self):
        chapter_slug = self.kwargs.get("slug")
        return get_object_or_404(Chapter, slug=chapter_slug)

    @property
    def success_url(self):
        chapter_slug = self.kwargs.get("slug")
        return reverse("chapter-manage", args=[chapter_slug])

    def get_permission_object(self):
        return self.chapter

    def get_object(self):
        queryset = self.get_queryset()
        username = self.kwargs.get("username")
        try:
            return queryset.filter(user__username=username, chapter=self.chapter).get()
        except queryset.model.DoesNotExist:
            raise Http404("No GameRole found matching the query")


class CreateRulesetView(AutoPermissionRequiredMixin, CreateView):
    model = Ruleset
    fields = ["package", "enabled"]
    success_url = reverse_lazy("game-manage")
    permission_required = "game.change_game"

    def get_permission_object(self):
        return self.request.game

    def get_object(self):
        return Ruleset(game=self.request.game)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.game = self.request.game
        try:
            engine: Engine = self.object.engine
            if engine.ruleset.bad_defs:
                form.add_error(
                    "package",
                    f"Bad definitions exist in ruleset: {engine.ruleset.bad_defs}",
                )
        except Exception as exc:
            form.add_error("package", f"Error loading ruleset: {exc}")
        return super().form_valid(form)


class UpdateRulesetView(AutoPermissionRequiredMixin, UpdateView):
    model = Ruleset
    fields = ["package", "enabled"]
    success_url = reverse_lazy("game-manage")


class DeleteRulesetView(AutoPermissionRequiredMixin, DeleteView):
    model = Ruleset
    success_url = reverse_lazy("game-manage")


class CreateGameRoleView(AutoPermissionRequiredMixin, CreateView):
    model = GameRole
    success_url = reverse_lazy("game-manage")
    fields = ["user", "title", "manager", "auditor", "rules_staff"]
    permission_required = "game.change_game"

    def get_permission_object(self):
        return self.request.game

    def form_valid(self, form):
        """If the form is valid, save the associated model."""
        # You don't get to choose which Game the role applies to.
        # Intercept the model to set the Game manually before saving.
        self.object = form.save(commit=False)
        self.object.game = self.request.game
        try:
            self.object.save()
        except IntegrityError:
            form.add_error("user", "User already has a role for this game.")
            return super().form_invalid(form)
        return super().form_valid(form)


class UpdateGameRoleView(AutoPermissionRequiredMixin, UpdateView):
    model = GameRole
    success_url = reverse_lazy("manage-game")
    fields = ["title", "manager", "auditor", "rules_staff"]
    queryset = GameRole.objects.select_related("user", "game")

    def get_object(self):
        queryset = self.get_queryset()
        username = self.kwargs.get("username")
        game = self.request.game
        try:
            return queryset.filter(user__username=username, game=game).get()
        except queryset.model.DoesNotExist:
            raise Http404("No GameRole found matching the query")


class DeleteGameRoleView(AutoPermissionRequiredMixin, DeleteView):
    model = GameRole
    success_url = reverse_lazy("manage-game")
    queryset = GameRole.objects.select_related("user", "game")

    def get_object(self):
        queryset = self.get_queryset()
        username = self.kwargs.get("username")
        game = self.request.game
        try:
            return queryset.filter(user__username=username, game=game).get()
        except queryset.model.DoesNotExist:
            raise Http404("No GameRole found matching the query")


class CampaignView(AutoPermissionRequiredMixin, DetailView):
    model = Campaign


class CreateCampaignView(AutoPermissionRequiredMixin, CreateView):
    model = Campaign

    fields = ["slug", "name", "description", "start_year", "is_open", "ruleset"]

    def get_permission_object(self):
        return self.request.game

    @property
    def success_url(self):
        if self.object:
            return reverse("campaign-update", args=[self.object.slug])
        return "/"

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.game = self.request.game
        self.object.save()
        return super().form_valid(form)


class UpdateCampaignView(AutoPermissionRequiredMixin, UpdateView):
    model = Campaign
    fields = ["slug", "name", "description", "start_year", "is_open", "ruleset"]

    @property
    def success_url(self):
        if self.object:
            return reverse("campaign-update", args=[self.object.slug])
        return "/"


class DeleteCampaignView(AutoPermissionRequiredMixin, DeleteView):
    model = Campaign
    fields = ["slug", "name", "description", "is_open", "ruleset"]

    @property
    def success_url(self):
        if self.object:
            return reverse("campaign-update", args=[self.object.slug])
        return "/"


@login_required
@require_http_methods(["GET", "POST"])
def myawards_view(request, slug):
    context = {}
    context["campaign"] = campaign = get_object_or_404(Campaign, slug=slug)

    with transaction.atomic():
        claimable, unclaimable = Award.unclaimed_for(request.user, campaign)
        characters = request.user.characters.filter(campaign=campaign)

        if request.method == "POST":
            try:
                claim_ids = [int(c) for c in request.POST.getlist("claim_award", [])]
            except ValueError:
                return http.HttpResponseBadRequest("Invalid claim award list")
            awards = claimable.filter(id__in=claim_ids)
            if awards:
                # If a character was specified, it must be one this player owns from the
                # appropriate campaign. If it's not specified, create one.
                character_id = request.POST.get("character", None)
                if character_id is None or character_id == "":
                    new_name = request.POST.get("new_name", "")
                    character = Character.objects.create(
                        name=new_name,
                        game=request.game,
                        campaign=campaign,
                        owner=request.user,
                    )
                    messages.info(request, f"Created character '{character}'")
                else:
                    try:
                        character_id = int(character_id)
                        character = characters.get(id=character_id)
                    except (ValueError, Character.DoesNotExist):
                        return http.HttpResponseBadRequest("Invalid character ID")

                for a in awards:
                    a.claim(request.user, character)
                messages.success(
                    request, f"Claimed {len(awards)} award(s) for {character}"
                )

                # Preserve the character selection between actions
                context["selected_character"] = character.id

                # Update the list of awards and characters, since both may have changed.
                claimable, unclaimable = Award.unclaimed_for(request.user, campaign)
                characters = request.user.characters.filter(campaign=campaign)
            else:
                messages.warning(request, "No valid awards selected.")

    context["characters"] = list(characters.filter(discarded_date=None))
    charmap = {c.id: c for c in characters}
    context["claimable"] = list(claimable)
    context["unclaimable"] = list(unclaimable)
    context["player"] = player = PlayerCampaignData.retrieve_model(
        request.user, campaign, update=False
    ).record
    context["award_history"] = [
        (award, charmap.get(award.character, None)) for award in player.awards
    ]

    context["unclaimable_award_count"] = unclaimable.count()
    context["unclaimable_award_emails"] = sorted({a.email.lower() for a in unclaimable})
    return render(request, "game/myawards.html", context)


@permission_required("game.add_award", _get_game, raise_exception=True)
@require_http_methods(["GET", "POST"])
def grant_award(request, slug):
    campaign = get_object_or_404(Campaign, slug=slug)
    context = {"campaign": campaign, "step": 1}
    template = "game/grant_award.html"

    if request.method == "GET":
        context["form"] = forms.AwardPlayerStep(initial=request.GET)
        return render(request, template, context)
    else:
        # Pick the form class depending on what step we're on.
        current_step = int(request.POST["step"])

        # Always check that the base form is still valid.
        step1_form = forms.AwardPlayerStep(request.POST)
        if not step1_form.is_valid():
            context["form"] = step1_form
            return render(request, template, context)

        category = step1_form.cleaned_data["award_category"]
        player = step1_form.cleaned_data.get("player")
        email = step1_form.cleaned_data.get("email")

        if email:
            # Check if we can resolve the email to a verified account.
            if address := EmailAddress.objects.filter(email=email).first():
                if address.verified:
                    player = address.user
                    email = None
                else:
                    context["maybe_player"] = maybe_player = address.user
                    context["maybe_profile"] = Membership.find(request, maybe_player)

        if player:
            characters = Character.objects.filter(
                campaign=campaign, owner=player, discarded_date=None
            )
            context["profile"] = Membership.find(request, player)
        else:
            # No character selection if we're doing email-based awards.
            # The player will select one when they claim it.
            characters = None

        initial = {
            "player": player,
            "email": email,
            "award_category": category,
        }

        context.update(initial)
        context["category_label"] = forms.CATEGORY_CHOICE_DICT.get(category)

        # If step 2 data was submitted, we'll validate it.
        # Otherwise we'll return fresh Step 2 forms with the previous
        # step's initial data loaded.
        if current_step > 1:
            data = request.POST
        else:
            data = None

        if category == AwardCategory.EVENT:
            # TODO: Only show events in the list if the current user
            # would normally be allowed to control them.
            events = Event.objects.filter(campaign=campaign, completed=True).order_by(
                "-event_end_date"
            )
            form = forms.AwardEventStep(
                data=data,
                initial=initial,
                character_query=characters,
                event_query=events,
            )
        elif category == AwardCategory.PLOT:
            form = forms.AwardPlotStep(
                data=data,
                initial=initial,
                character_query=characters,
            )
        else:
            # Someone's been tricky. Return to start.
            context["form"] = step1_form
            return render(request, template, context)

        context["form"] = form
        context["step"] = 2

        if current_step == 1:
            # Return the fresh step 2 form.
            return render(request, template, context)

        # Otherwise, try to finish the grant.
        if form.is_valid():
            form.create_award(campaign, request)
            messages.success(request, "Award created successfully.")
            # TODO: Redirect somewhere better
            return redirect("home")
        return render(request, template, context)
