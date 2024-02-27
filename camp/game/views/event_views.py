import datetime
import io
import logging

from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse
from django.http import Http404
from django.http import HttpResponseBadRequest
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST
from django_htmx.http import HttpResponseClientRefresh
from rules.contrib.views import objectgetter
from rules.contrib.views import permission_required

from camp.accounts.forms import MembershipForm
from camp.accounts.models import Membership
from camp.accounts.models import User
from camp.character.models import Character

from .. import forms
from .. import models
from .. import tasks


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
    if event.completed:
        messages.warning(request, "Events can't be edited once complete.")
        return redirect("event-detail", pk=pk)
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
            event: models.Event = form.save(commit=False)
            event.creator = request.user
            event.save()
            return redirect(event)
    else:
        form = forms.EventCreateForm(instance=event)
    return render(request, "events/event_form.html", {"form": form})


@permission_required(
    "game.change_event", fn=objectgetter(models.Event), raise_exception=True
)
@require_POST
def event_cancel(request, pk):
    event = _get_event(pk)

    if event.completed:
        messages.warning(
            request, "Event is already marked complete, a little late for that."
        )
    elif not event.canceled_date:
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


@permission_required(
    "game.change_event", fn=objectgetter(models.Event), raise_exception=True
)
@require_POST
def mark_event_complete(request, pk):
    event = get_object_or_404(models.Event, pk=pk)
    event.mark_complete()
    return HttpResponseClientRefresh()


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


@permission_required(
    "game.change_event", fn=objectgetter(models.Event), raise_exception=True
)
def view_registration(request, pk, username):
    """View a user's registration.

    This view is for logistics, and should have a few functions:

    1. Edit registration, maybe?
    2. Cancel registration.
    3. Make notes, mark as paid, etc.
    4. Print character sheet.
    """
    event = _get_event(pk)
    player = get_object_or_404(User, username=username)
    registration = event.get_registration(player)
    membership = Membership.objects.filter(game=request.game, user=player).first()
    if registration is None:
        # TODO: Consider allowing logistics to register on behalf of a user who hasn't
        # registered yet, including potentially creating their character/profile/account.
        raise Http404

    if request.method == "GET":
        reg_form = forms.RegisterForm(instance=registration, allow_payment=True)
    elif request.method == "POST":
        reg_form = forms.RegisterForm(
            request.POST, instance=registration, allow_payment=True
        )
        if reg_form.is_valid():
            registration = reg_form.save(commit=False)
            if registration.character is None:
                registration.character = Character.objects.create(
                    owner=registration.user,
                    campaign=event.campaign,
                    game=event.campaign.game,
                )
            registration.save()
            return redirect("registration-list", pk=event.pk)
    else:
        return HttpResponseNotAllowed(("GET", "POST"))

    return render(
        request,
        "events/registration_view.html",
        context={
            "event": event,
            "player": player,
            "profile": membership,
            "registration": registration,
            "reg_form": reg_form,
            "character": registration.character,
        },
    )


@permission_required(
    "game.change_event", fn=objectgetter(models.Event), raise_exception=True
)
def list_registrations(request, pk):
    """View registrations for an event.

    This view is for logistics.

    1. Bulk operations (print character sheet).
    2. Report generators (income, skills, new characters, and so on).
    3. (After event): Attendance recording.
    """
    event = _get_event(pk)

    if request.method == "POST":
        # Handle bulk actions
        match apply := request.POST.get("apply", "none"):
            case "mark_paid":
                _mark_paid(request, event)
            case "mark_unpaid":
                _mark_unpaid(request, event)
            case "mark_attendance":
                _mark_attended(request, event)
            case _:
                messages.warning(request, f"Unregistered action '{apply}'")
        return redirect("registration-list", pk=event.pk)

    registrations = event.registrations.order_by(
        "canceled_date", "is_npc", "registered_date"
    ).prefetch_related("user", "character")

    pc_count = sum(
        1 if r.canceled_date is None and not r.is_npc else 0 for r in registrations
    )
    npc_count = sum(
        1 if r.canceled_date is None and r.is_npc else 0 for r in registrations
    )
    withdrew_count = sum(1 if r.canceled_date is not None else 0 for r in registrations)

    report = _fetch_report(pk, "registration_list")

    can_complete, _ = event.can_complete()

    return render(
        request,
        "events/registration_list.html",
        context={
            "event": event,
            "registrations": registrations,
            "pc_count": pc_count,
            "npc_count": npc_count,
            "withdrew_count": withdrew_count,
            "report": report,
            "can_complete": can_complete,
        },
    )


@permission_required(
    "game.change_event", fn=objectgetter(models.Event), raise_exception=True
)
@require_POST
def trigger_event_report(request, pk, report_type):
    event = get_object_or_404(models.Event, pk=pk)

    if existing_report := _fetch_report(pk, report_type):
        if result := existing_report.result:
            result.revoke()
            result.forget()
            existing_report.delete()

    logging.info("Triggering generate_report task for %s, %s", pk, report_type)
    try:
        report, result = tasks.generate_report(
            report_type=report_type,
            event_id=pk,
            requestor=request.user.username,
            base_url=request.get_host(),
        )
    except KeyError:
        return HttpResponseBadRequest(f"Unknown report type {report_type}")

    # Check if we should skip polling and go for the download immediately
    if result.ready:
        report.refresh_from_db(fields=["download_ready"])

    return render(
        request,
        "events/event_report_progress.html",
        {"report": report, "event": event},
    )


@permission_required(
    "game.change_event", fn=objectgetter(models.Event), raise_exception=True
)
@require_GET
def poll_event_report(request, pk, report_type):
    event = get_object_or_404(models.Event, pk=pk)
    report = _fetch_report(pk, report_type)
    return render(
        request, "events/event_report_progress.html", {"report": report, "event": event}
    )


@permission_required(
    "game.change_event", fn=objectgetter(models.Event), raise_exception=True
)
@require_GET
def download_event_report(request, pk, report_type):
    report = _fetch_report(pk, report_type)
    if report and report.download_ready:
        if report.task_id:
            result = AsyncResult(report.task_id)
            result.forget()
        return _report_download_response(report)
    return Http404


def _fetch_report(event_id, report_type) -> models.EventReport | None:
    # Check for existing reports (and clean old ones if needed)
    reports = (
        models.EventReport.objects.filter(
            event_id=event_id,
            report_type=report_type,
        )
        .defer("blob")
        .order_by("-started")
        .all()
    )
    # TODO: If we have multiple report types, show the latest of each.
    if reports:
        report = reports[0]
        logging.debug("Report found for event %s: %r", event_id, report)
        for old_report in reports[1:]:
            logging.info(
                "Cleaning up old report: %s from %s", old_report.pk, old_report.started
            )
            old_report.result.revoke()
            old_report.result.forget()
            old_report.delete()
        if report.result.failed():
            logging.info(
                "Cleaning up failed report: %s from %s", report.pk, report.started
            )
            report.result.forget()
            report.delete()
            report = None
    else:
        logging.debug("No reports found for event %s", event_id)
        report = None
    return report


def _report_download_response(report: models.EventReport) -> FileResponse:
    stream = io.BytesIO(report.blob)
    stream.seek(0)
    return FileResponse(
        stream,
        as_attachment=True,
        content_type=report.content_type,
        filename=report.filename,
    )


@transaction.atomic
def _mark_paid(request, event):
    usernames = request.POST.getlist("selected", [])
    users = User.objects.filter(username__in=usernames)
    reg: models.EventRegistration
    today = datetime.date.today()
    count = 0
    for reg in event.registrations.filter(payment_complete=False, user__in=users):
        count += 1
        reg.payment_complete = True
        if prev_note := reg.payment_note:
            reg.payment_note = f"Marked paid by {request.user.username} on {today}\nPrevious note:\n{prev_note}"
        else:
            reg.payment_note = f"Marked paid by {request.user.username} on {today}"
        reg.save()
    transaction.on_commit(
        lambda: messages.success(request, f"Marked {count} users paid.")
    )


@transaction.atomic
def _mark_unpaid(request, event):
    usernames = request.POST.getlist("selected", [])
    users = User.objects.filter(username__in=usernames)
    reg: models.EventRegistration
    today = datetime.date.today()
    count = 0
    for reg in event.registrations.filter(payment_complete=True, user__in=users):
        count += 1
        reg.payment_complete = False
        if prev_note := reg.payment_note:
            reg.payment_note = f"Marked unpaid by {request.user.username} on {today}\nPrevious note:\n{prev_note}"
        else:
            reg.payment_note = f"Marked paid by {request.user.username} on {today}"
        reg.save()
    transaction.on_commit(
        lambda: messages.success(request, f"Marked {count} users unpaid.")
    )


@transaction.atomic
def _mark_attended(request, event):
    usernames = request.POST.getlist("selected", [])
    users = User.objects.filter(username__in=usernames)
    reg: models.EventRegistration
    count = 0
    skipped = 0
    for reg in event.registrations.filter(user__in=users):
        if not reg.attended:
            count += 1
            reg.apply_award(applied_by=request.user)
            reg.save()
        else:
            skipped += 1
    if skipped:
        transaction.on_commit(
            lambda: messages.success(
                request, f"Marked {count} attended. {skipped} were already marked."
            )
        )
    else:
        transaction.on_commit(
            lambda: messages.success(request, f"Marked {count} attended.")
        )


def _get_event(pk):
    return get_object_or_404(
        models.Event.objects.prefetch_related("campaign", "chapter"), pk=pk
    )
