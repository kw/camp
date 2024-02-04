from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from rules.contrib.views import permission_required

from .forms import MembershipForm
from .models import Membership
from .models import User


@login_required
def my_profile(request):
    membership = Membership.find(request)
    return render(
        request,
        "account/profile_detail.html",
        context={"user": request.user, "membership": membership},
    )


@login_required
def profile_edit(request):
    initial = {}
    if not (membership := Membership.find(request)):
        membership = Membership(game=request.game, user=request.user)
        initial = {"legal_name": request.user.get_full_name()}

    if request.method == "GET":
        form = MembershipForm(instance=membership, initial=initial)
    elif request.method == "POST":
        form = MembershipForm(request.POST, instance=membership, initial=initial)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile successfully updated.")
            return redirect("account_profile")

    return render(request, "account/profile_form.html", context={"form": form})


def _get_game(request, username):
    return request.game


@permission_required("accounts.view_membership", _get_game, raise_exception=True)
def profile_view(request, username):
    """This view is currently only for staff, as it includes sensitive data."""
    player = get_object_or_404(User, username=username)
    profile = Membership.find(request, user=player)
    emails = player.emailaddress_set.order_by("-primary", "-verified")
    return render(
        request,
        "account/profile_view.html",
        {"player": player, "profile": profile, "emails": emails},
    )
