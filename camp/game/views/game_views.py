from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.generic import DeleteView
from django.views.generic import DetailView
from django.views.generic import UpdateView
from rules.contrib.views import AutoPermissionRequiredMixin

from camp.character.models import Character
from camp.engine.rules.base_engine import Engine

from ..models import Award
from ..models import Campaign
from ..models import Chapter
from ..models import ChapterRole
from ..models import Game
from ..models import GameRole
from ..models import Ruleset


def home_view(request):
    game = request.game
    context = {"game": game}

    if request.user.is_authenticated:
        context["character_list"] = Character.objects.filter(
            owner=request.user,
            discarded_date=None,
        )
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
