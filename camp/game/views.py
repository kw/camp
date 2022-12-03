from django.db import IntegrityError
from django.http import Http404
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.generic import DeleteView
from django.views.generic import DetailView
from django.views.generic import UpdateView
from rules.contrib.views import AutoPermissionRequiredMixin

from .models import Game
from .models import GameRole


class HomePageView(DetailView):
    model = Game
    template_name_suffix = "_home"

    def get_object(self):
        return self.request.game


class ManageGameView(AutoPermissionRequiredMixin, UpdateView):
    model = Game
    fields = ["name", "description", "is_open"]
    success_url = "/"

    def get_object(self):
        return self.request.game


class CreateGameRoleView(AutoPermissionRequiredMixin, CreateView):
    model = GameRole
    success_url = reverse_lazy("manage-game")
    fields = ["user", "title", "manager", "auditor", "rules_staff"]
    template_name_suffix = "_add_form"
    permission_required = "game.change_game"

    def get_permission_object(self):
        return self.request.game

    def get_object(self):
        return GameRole(game=self.request.game)

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
    template_name_suffix = "_update_form"
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
