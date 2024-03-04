import datetime
import io
from typing import Iterable
from urllib.parse import urljoin

import celery
from celery import shared_task
from celery.result import AsyncResult
from xlsxwriter import Workbook

from camp.accounts.models import User

from . import models

_WORKBOOK_OPTIONS = {
    "constant_memory": False,
    "remove_timezone": True,
    "default_date_format": "dd mmm yyyy",
}

_XLSLX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_FILENAME_TABLE = str.maketrans(
    {
        "/": "⁄",
        "\\": "⁄",
        "<": "❮",
        ">": "❯",
        "{": "❴",
        "}": "❵",
        ":": "ː",
        "|": "❘",
        "?": "❓",
        "*": "✳",
    }
)


def generate_report(
    report_type, event_id, requestor, **kwargs
) -> tuple[models.EventReport, AsyncResult]:
    task: celery.Task
    match report_type:
        case "registration_list":
            task = _export_registrations
        case _:
            raise KeyError(f"Unknown report type {report_type}")
    user = User.objects.filter(username=requestor).first()
    report = models.EventReport.objects.create(
        event_id=event_id, requestor=user, report_type=report_type
    )
    kwargs["report_id"] = report.id
    result = task.apply_async(kwargs=kwargs, task_id=report.task_id)
    return report, result


@shared_task(bind=True)
def _export_registrations(self: celery.Task, report_id: int, base_url: str = "") -> int:
    report = models.EventReport.objects.get(pk=report_id)
    event = report.event
    all_regs = list(event.registrations.filter(canceled_date__isnull=True).all())
    stream = io.BytesIO()
    user = report.requestor
    with Workbook(stream, _WORKBOOK_OPTIONS) as wb:
        wb.set_properties(
            {
                "title": f"Registrations for {event}",
                "author": __name__,
                "manager": user.username if user else "(unknown)",
                "created": datetime.date.today(),
            }
        )
        header_format = wb.add_format({"bold": True})
        _write_pc_regs(
            wb, header_format, base_url, (r for r in all_regs if not r.is_npc)
        )
        _write_npc_regs(wb, header_format, base_url, (r for r in all_regs if r.is_npc))
    report.blob = stream.getvalue()
    report.content_type = _XLSLX_MIMETYPE
    report.filename = _filenameize(f"{event} Registrations.xlsx")
    report.download_ready = True
    report.save()
    return report.pk


def _write_pc_regs(
    wb: Workbook,
    header_format,
    base_url: str,
    regs: Iterable[models.EventRegistration],
):
    sheet = wb.add_worksheet("PC Registrations")
    # Write header
    sheet.write_row(
        0,
        0,
        [
            "Username",
            "Name",
            "Minor?",
            "Attendance",
            "Lodging",
            "Character",
            "New Player?",
            "New Character?",
            "Paid?",
            "Registered",
            "Link to Registration",
        ],
        header_format,
    )
    sheet.freeze_panes(1, 1)
    for i, r in enumerate(regs, start=1):
        user = r.user
        profile = r.profile
        age = profile.age if profile.age < 18 else None
        char = r.character
        new_character = r.character_is_new
        new_player = r.player_is_new
        paid = r.payment_complete
        reg_date = r.registered_date

        sheet.write(i, 0, user.username)
        sheet.write(i, 1, str(profile))
        sheet.write(i, 2, age)
        sheet.write(i, 3, r.get_attendance_display())
        sheet.write(i, 4, r.get_lodging_display())
        if char:
            sheet.write_url(
                i, 5, urljoin(base_url, char.get_absolute_url()), string=char.name
            )
        else:
            sheet.write(i, 5, "No Character")
        sheet.write(i, 6, new_player)
        sheet.write(i, 7, new_character)
        sheet.write(i, 8, paid)
        sheet.write(i, 9, reg_date)
        sheet.write_url(
            i,
            10,
            urljoin(base_url, r.get_absolute_url()),
            string=f"Registration for {profile}",
        )
    sheet.autofit()


def _write_npc_regs(
    wb: Workbook, header_format, base_url: str, regs: Iterable[models.EventRegistration]
):
    sheet = wb.add_worksheet("NPC Registrations")
    # Write header
    sheet.write_row(
        0,
        0,
        [
            "Username",
            "Name",
            "Minor?",
            "Attendance",
            "Lodging",
            "New Player?",
            "New NPC?",
            "Registered",
            "Link to Registration",
        ],
        header_format,
    )
    sheet.freeze_panes(1, 1)
    for i, r in enumerate(regs, start=1):
        user = r.user
        profile = r.profile
        age = profile.age if profile.age < 18 else None
        new_player = r.player_is_new
        new_npc = r.npc_is_new
        reg_date = r.registered_date

        sheet.write(i, 0, user.username)
        sheet.write(i, 1, str(profile))
        sheet.write(i, 2, age)
        sheet.write(i, 3, r.get_attendance_display())
        sheet.write(i, 4, r.get_lodging_display())
        sheet.write(i, 5, new_player)
        sheet.write(i, 6, new_npc)
        sheet.write(i, 7, reg_date)
        sheet.write_url(
            i,
            8,
            urljoin(base_url, r.get_absolute_url()),
            string=f"Registration for {profile}",
        )
    sheet.autofit()


def _filenameize(string: str) -> str:
    return string.translate(_FILENAME_TABLE)
