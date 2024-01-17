from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from rules.contrib.views import objectgetter
from rules.contrib.views import permission_required

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
    return render(request, "events/event_detail.html", {"event": event})


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


def _get_event(pk):
    return get_object_or_404(
        models.Event.objects.prefetch_related("campaign", "chapter"), pk=pk
    )
