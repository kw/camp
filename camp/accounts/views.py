from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy

# from django.shortcuts import get_object_or_404
# from django.shortcuts import redirect
# from django.shortcuts import render
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView
from django.views.generic.edit import DeleteView
from django.views.generic.edit import UpdateView
from django.views.generic.list import ListView

from .models import Membership


class ProfileDetailView(LoginRequiredMixin, DetailView):
    model = get_user_model()
    template_name = "account/profile_detail.html"

    def get_object(self):
        return self.request.user


class MembershipListView(ListView):
    model = Membership


class MembershipDetailView(DetailView):
    model = Membership


class MembershipCreateView(CreateView):
    model = Membership
    fields = ["joined", "nickname", "game", "user"]
    success_url = reverse_lazy("membership-list")


class MembershipUpdateView(UpdateView):
    model = Membership
    fields = ["joined", "nickname", "game", "user"]
    success_url = reverse_lazy("membership-list")


class MembershipDeleteView(DeleteView):
    model = Membership
    context_object_name = "membership"
    success_url = reverse_lazy("membership-list")
