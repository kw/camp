import datetime
import io
from typing import Iterable
from urllib.parse import urljoin

from celery import shared_task
from xlsxwriter import Workbook

from . import models

_WORKBOOK_OPTIONS = {
    "constant_memory": False,
    "remove_timezone": True,
    "default_date_format": "dd mmm yyyy",
}


@shared_task
def export_registrations(
    event_pk: int, requestor: str, base_url: str = "", filename: str | None = None
):
    event = models.Event.objects.get(pk=event_pk)
    all_regs = list(event.registrations.filter(canceled_date__isnull=True).all())
    if filename is None:
        io_or_filename = io.BytesIO()
    else:
        io_or_filename = filename
    with Workbook(io_or_filename, _WORKBOOK_OPTIONS) as wb:
        wb.set_properties(
            {
                "title": f"Registrations for {event}",
                "author": __name__,
                "manager": requestor,
                "created": datetime.date.today(),
            }
        )
        header_format = wb.add_format({"bold": True})
        _write_pc_regs(
            wb, header_format, base_url, (r for r in all_regs if not r.is_npc)
        )
        _write_npc_regs(wb, header_format, base_url, (r for r in all_regs if r.is_npc))
    if filename is None:
        return io_or_filename.getvalue()


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
        if char := r.character:
            new_character = True  # TODO: Implement
        else:
            new_character = True
        new_player = True  # TODO: Implement
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
        new_player = True  # TODO: Implement
        reg_date = r.registered_date

        sheet.write(i, 0, user.username)
        sheet.write(i, 1, str(profile))
        sheet.write(i, 2, age)
        sheet.write(i, 3, r.get_attendance_display())
        sheet.write(i, 4, r.get_lodging_display())
        sheet.write(i, 5, new_player)
        sheet.write(i, 6, reg_date)
        sheet.write_url(
            i,
            7,
            urljoin(base_url, r.get_absolute_url()),
            string=f"Registration for {profile}",
        )
    sheet.autofit()
