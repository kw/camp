from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.urls import reverse_lazy
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView
from django.views.generic.edit import DeleteView
from django.views.generic.edit import UpdateView
from django.views.generic.list import ListView
from rules.contrib.views import AutoPermissionRequiredMixin

from .models import Membership


class ProfileDetailView(LoginRequiredMixin, DetailView):
    model = get_user_model()
    template_name = "account/profile_detail.html"

    def get_object(self):
        return self.request.user


class MembershipListView(AutoPermissionRequiredMixin, ListView):
    permission_type_map = [
        (CreateView, "add"),
        (UpdateView, "change"),
        (DeleteView, "delete"),
        (DetailView, "view"),
        (ListView, "view"),
    ]

    model = Membership
    template_name = "account/membership_list.html"
    context_object_name = "membership_list"

    def get_queryset(self):
        queryset = Membership.objects.all()
        return queryset.filter(user=self.request.user)


class MembershipDetailView(AutoPermissionRequiredMixin, DetailView):
    model = Membership
    template_name = "account/membership_detail.html"


class MembershipCreateView(AutoPermissionRequiredMixin, CreateView):
    model = Membership
    fields = ["nickname"]
    success_url = reverse_lazy("membership-list")
    template_name = "account/membership_create.html"

    def form_valid(self, form):
        # You don't get to choose which Game the Membership applies to.
        # Intercept the model to set the Game manually before saving.
        self.object = form.save(commit=False)
        self.object.user = self.request.user
        self.object.game = self.request.Game
        try:
            self.object.save()
        except IntegrityError:
            form.add_error("user", "User already has a membership for this game.")
            return super().form_invalid(form)
        return super().form_valid(form)


class MembershipUpdateView(AutoPermissionRequiredMixin, UpdateView):
    model = Membership
    fields = ["nickname"]
    success_url = reverse_lazy("membership-list")
    template_name = "account/membership_update.html"

    def form_valid(self, form):
        # You don't get to choose which Game the Membership applies to.
        # Intercept the model to set the Game manually before saving.
        self.object = form.save(commit=False)
        self.object.user = self.request.user
        return super().form_valid(form)


class MembershipDeleteView(AutoPermissionRequiredMixin, DeleteView):
    model = Membership
    context_object_name = "membership"
    success_url = reverse_lazy("membership-list")
