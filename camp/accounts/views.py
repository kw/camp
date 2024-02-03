from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.shortcuts import render

from .forms import MembershipForm
from .models import Membership


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
