from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from rules.contrib.views import objectgetter
from rules.contrib.views import permission_required

from camp.accounts.forms import MembershipForm
from camp.accounts.models import Membership
from camp.character.models import Character

from .. import forms
from .. import models


def event_list(request):
    chapters = request.game.chapters.order_by("name")
    chapter_events = [(c, c.events.order_by("event_start_date")) for c in chapters]
    return render(request, "events/event_list.html", {"chapter_events": chapter_events})


@permission_required(
    "game.view_event", fn=objectgetter(models.Event), raise_exception=True
)
def event_detail(request, pk):
    event = _get_event(pk)
    registration = event.get_registration(request.user)
    return render(
        request,
        "events/event_detail.html",
        {"event": event, "registration": registration},
    )


@permission_required(
    "game.change_event", fn=objectgetter(models.Event), raise_exception=True
)
def event_edit(request, pk):
    event = _get_event(pk)
    chapter = event.chapter
    _ = event.campaign
    timezone.activate(chapter.timezone)
    if request.method == "POST":
        form = forms.EventUpdateForm(request.POST, instance=event)
        if form.is_valid():
            event = form.save()
            return redirect(event)
    else:
        form = forms.EventUpdateForm(instance=event)
    return render(request, "events/event_form.html", {"form": form, "event": event})


@permission_required(
    "game.add_event",
    fn=objectgetter(models.Chapter, attr_name="slug", field_name="slug"),
    raise_exception=True,
)
def event_create(request, slug):
    chapter = get_object_or_404(models.Chapter, slug=slug)
    timezone.activate(chapter.timezone)
    event = models.Event(chapter=chapter)
    if request.method == "POST":
        form = forms.EventCreateForm(request.POST, instance=event)
        if form.is_valid():
            event = form.save()
            return redirect(event)
    else:
        form = forms.EventCreateForm(instance=event)
    return render(request, "events/event_form.html", {"form": form})


@permission_required(
    "game.change_event", fn=objectgetter(models.Event), raise_exception=True
)
def event_cancel(request, pk):
    if request.method == "GET":
        # Don't allow an event to be canceled via GET
        return redirect("event-update", pk=pk)

    event = _get_event(pk)

    if not event.canceled_date:
        event.canceled_date = timezone.now()
        event.save()
        messages.warning(request, "Event canceled.")
    else:
        messages.error("Event was already canceled.")
    return redirect("events-list")


@permission_required(
    "game.change_event", fn=objectgetter(models.Event), raise_exception=True
)
def event_uncancel(request, pk):
    if request.method == "GET":
        # Don't allow an event to be uncanceled via GET
        return redirect("event-update", pk=pk)

    event = _get_event(pk)

    if event.canceled_date:
        event.canceled_date = None
        event.save()
        messages.success(request, "Event re-opened.")
    else:
        messages.warning(request, "Event had not been canceled, so good?")
    return redirect(event)


@login_required
def register_view(request, pk):
    """Event Registration Form.

    There are several use cases around event registration:

    1. I want to register for an event!
        a. I have/do not have a character already.
        b. I want to PC/NPC
        c. I want to pay for the event (in the future, for now, link to a shop item).
        d. I want to register a minor in my care (future, for now, log in as them).
    2. I want to modify my existing registration.
        a. Has the registration period closed?
        b. Has the event already started/ended?
        c. Has data already been exported?
        d. I want to switch between PC and NPCing
        e. (later) I want to change my payment (because I switched PC/NPC)
    3. I want to cancel my registration for an event.
        a. Has the registration period closed?
        b. (later) Has a payment already been made?
    4. Maybe we should send an email?
    5. Might want to support some types of non-game events ("meetups") that don't involve
       things like characters, PC/NPC distinctions, lodging, etc.
    6. I don't have a profile yet / I want to review or edit my profile while registering
    """
    event = _get_event(pk)

    registration = event.get_registration(request.user)
    if not registration:
        registration = models.EventRegistration(
            event=event,
            user=request.user,
            details=event.details_template,
        )

    membership = Membership.find(request) or Membership(
        game=request.game, user=request.user
    )
    needs_profile = membership.pk is None

    if request.method == "GET":
        form = forms.RegisterForm(instance=registration, prefix="reg")
        profile_form = MembershipForm(instance=membership, prefix="profile")
    elif request.method == "POST":
        form = forms.RegisterForm(request.POST, instance=registration, prefix="reg")
        profile_form = MembershipForm(
            request.POST, instance=membership, prefix="profile"
        )
        if not event.registration_window_open():
            messages.error(request, "Registration window is closed, sorry.")
        else:
            if profile_form.is_valid():
                membership = profile_form.save()
                needs_profile = False
            else:
                needs_profile = True

            if form.is_valid():
                registration: models.EventRegistration = form.save(commit=False)
                is_initial_registration = registration.pk is None

                character = registration.character
                character_created = False

                # If the registration had previously been withdrawn, clear that.
                is_resubmit = registration.is_canceled
                registration.canceled_date = None

                # If no character was selected, pick or create one.
                if character is None:
                    character = form.fields["character"].queryset.first()
                    if not character:
                        character_created = True
                        character = Character.objects.create(
                            owner=registration.user,
                            campaign=event.campaign,
                            game=event.campaign.game,
                        )
                    registration.character = character

                registration.sheet = registration.character.primary_sheet

                registration.save()

                if is_initial_registration:
                    messages.success(request, f"Registered for {event}!")
                    if character_created and not registration.is_npc:
                        # They should probably make their character...
                        messages.info(request, "Created a blank character sheet.")
                        return redirect(character)
                elif is_resubmit:
                    messages.success(request, "Registration resubmitted.")
                else:
                    messages.success(request, "Registration updated.")
                return redirect(event)

    # Disable the form elements if registration is closed.
    if not event.registration_window_open():
        for field in form.fields.values():
            field.disabled = True

    return render(
        request,
        "events/register_form.html",
        {
            "form": form,
            "registration": registration,
            "profile_form": profile_form,
            "needs_profile": needs_profile,
        },
    )


@login_required
def unregister_view(request, pk):
    if request.method == "GET":
        # Don't allow a registration to be unregistered via GET
        return redirect("event-register", pk=pk)

    event = _get_event(pk)
    if not event.registration_window_open():
        # You can't cancel registration outside of the window.
        messages.warning(
            request, "Registration period is not open, registration is locked."
        )
        return redirect(event)

    if not (registration := event.get_registration(request.user)):
        messages.info(request, "You weren't registered for that event to begin with.")
        return redirect(event)

    if registration.canceled_date is None:
        registration.canceled_date = timezone.now()
        registration.save()
        messages.success(request, "Successfully unregistered.")
    else:
        messages.info(request, "You had already unregistered.")

    return redirect(event)


def view_registration(request, pk, user_id):
    """View a user's registration.

    This view is for logistics, and should have a few functions:

    1. Edit registration, maybe?
    2. Cancel registration.
    3. Make notes, mark as paid, etc.
    4. Print character sheet.
    """
    return redirect("events-list")


def list_registrations(request, pk):
    """View registrations for an event.

    This view is for logistics.

    1. Bulk operations (print character sheet).
    2. Report generators (income, skills, new characters, and so on).
    3. (After event): Attendance recording.
    """
    event = _get_event(pk)

    registrations = event.registrations.order_by("registered_date").prefetch_related(
        "user", "character"
    )

    return render(
        request,
        "events/registration_list.html",
        context={"event": event, "registrations": registrations},
    )


def _get_event(pk):
    return get_object_or_404(
        models.Event.objects.prefetch_related("campaign", "chapter"), pk=pk
    )
