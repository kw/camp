import datetime
import io
from typing import Any
from typing import Callable
from typing import Iterable
from urllib.parse import urljoin

from celery import chord
from celery import shared_task
from celery.result import AsyncResult
from sentry_sdk import add_breadcrumb
from sentry_sdk import capture_exception
from xlsxwriter import Workbook

from camp.accounts.models import User
from camp.character.models import Sheet
from camp.engine.rules.base_engine import PropertyController
from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter
from camp.engine.rules.tempest.controllers.feature_controller import FeatureController
from camp.game.models import Event

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


def _profession(char: TempestCharacter) -> str:
    master = char.feature_controller("profession-master")
    journeyman = char.feature_controller("profession-journeyman")
    apprentice = char.feature_controller("profession-apprentice")

    if master.value > 0:
        return f"{master.option} [Master]"
    if journeyman.value > 0:
        return f"{journeyman.option} [Journeyman]"
    for option, controller in apprentice.option_controllers().items():
        if controller.value > 0:
            return f"{option} [Apprentice]"
    return None


def _qualifiers(char: TempestCharacter) -> str:
    qualifiers = set()
    if char.get("demon-blood"):
        qualifiers.add("Demon")
    if char.get("fae-blood"):
        qualifiers.add("Fae")
    if char.get("draconic-heritage-1"):
        qualifiers.add("Dragon")
    if char.get("mechanical-augmentation"):
        qualifiers.add("Construct")
        qualifiers.add("Automaton")
    if char.get("druid") >= 10:
        qualifiers.add("Beast")
    if char.get("from-dusk-till-dawn") or char.get("curse-of-erasmus"):
        qualifiers.add("Hollow")
    return ", ".join(sorted(qualifiers))


def _attr(attr) -> str:
    def get_name(c: TempestCharacter) -> str:
        match v := getattr(c, attr, None):
            case None:
                return None
            case FeatureController():
                return v.display_name()
            case PropertyController():
                return v.value
            case _:
                return str(v)

    return get_name


def _true_format(c):
    return True if c.value > 0 else None


def _controller(expr: str, formatter=_true_format) -> Callable[[TempestCharacter], Any]:
    def get_controller(c: TempestCharacter) -> Any:
        if v := c.controller(expr):
            return formatter(v)
        return None

    return get_controller


def _display_format(c):
    return c.display_name() if c.value > 0 else None


def _option_format(c):
    if c.is_option_template:
        options = list(c.option_controllers())
        options.sort()
        return "; ".join(options)
    return None


def _best_of(
    exprs: list[str], formatter=_display_format
) -> Callable[[TempestCharacter], Any]:
    def get_controller(c: TempestCharacter) -> Any:
        for e in reversed(exprs):
            if (v := c.controller(e)) and v.value > 0:
                return formatter(v)
        return None

    return get_controller


def _craft(craftid):
    return _best_of(
        [
            f"apprentice-{craftid}",
            f"journeyman-{craftid}",
            f"greater-{craftid}",
            f"master-{craftid}",
        ]
    )


def _passive_income(char: TempestCharacter) -> int | None:
    # TODO: Move this logic into the feature definitions
    income = 0
    tax_evasion = char.get("tax-evasion") > 0
    if char.get("profession-apprentice") > 0:
        income += 4 if tax_evasion else 2
    if char.get("profession-journeyman") > 0:
        income += 6 if tax_evasion else 4
    if char.get("profession-master") > 0:
        income += 8 if tax_evasion else 6
    if char.get("income") > 0:
        income += 8 if tax_evasion else 7
    if tax_evasion and char.get("manse") > 0:
        # Manse doesn't grant *passive* income by itself,
        # unless you have Tax Evasion. You can _request_ Wealth
        # from it, though.
        income += 1
    if char.get("pit-master") > 0:
        income += 2
    # TODO: Add income from ACs
    return income


def _issues(char: TempestCharacter):
    if issues := char.issues():
        return f"{len(issues)} issues detected."
    return None


_CHARACTER_COLUMNS: dict[str, Callable[[TempestCharacter], Any]] = {
    "Issues": _issues,
    "Level": lambda c: c.level.value,
    "Religion": _attr("religion"),
    "Religion Level": lambda c: c.religion.level_label() if c.religion else None,
    "Culture": _attr("culture"),
    "Primary Breed": _attr("primary_breed"),
    "Subbreed": _attr("subbreed"),
    "Secondary Breed": _attr("secondary_breed"),
    "Primary Class": _attr("primary_class"),
    "Lores": _controller("lore", _option_format),
    "Profession": _profession,
    "Hobbies": _controller("chronic-hobbyist", _option_format),
    "Qualifiers/Types": _qualifiers,
    "Honor Debt": _controller("honor-debt", _option_format),
    "Sight?": _best_of(["sight", "sight-beyond-sight", "sensitive"]),
    "Locks?": _best_of(["basic-locks", "advanced-magical-locks"]),
    "Traps?": _best_of(["basic-traps", "advanced-traps"]),
    "Foraging": _best_of(["forage-1", "forage-2", "forage-3"]),
    "Prospecting": _best_of(["prospect-1", "prospect-2", "prospect-3"]),
    "Scavenging": _best_of(["scavenging-1", "scavenging-2", "scavenging-3"]),
    "Tinkering": _craft("tinkering"),
    "Alchemy": _craft("alchemy"),
    "Enchanting": _craft("enchanting"),
    "Arcane Ritual": _craft("arcane-ritual"),
    "Divine Ritual": _craft("divine-ritual"),
    "Tracking?": _controller("tracking"),
    "Nightmares?": _controller("nightmares"),
    "Rumormonger?": _controller("rumormonger"),
    "Manse?": _controller("manse"),
    "Patron?": _controller("patron"),
    "Sources?": _controller("sources"),
    "Fence?": _controller("fence"),
    "Inheritance?": _controller("inheritance"),
    "Passive Income": _passive_income,
    "Error": lambda c: None,
}


def generate_report(
    report_type, event_id, requestor, base_url, **kwargs
) -> tuple[models.EventReport, AsyncResult]:
    user = User.objects.filter(username=requestor).first()
    event = Event.objects.get(id=event_id)
    report = models.EventReport.objects.create(
        event=event,
        requestor=user,
        report_type=report_type,
    )

    event = report.event
    pc_regs = event.registrations.filter(
        canceled_date__isnull=True,
        is_npc=False,
        sheet__isnull=False,
    )

    result = chord(
        [sheet_columns.s(r.sheet_id) for r in pc_regs],
        task_id=report.task_id,
    )(
        export_registrations.s(report_id=report.id, base_url=base_url),
    )

    return report, result


@shared_task
def sheet_columns(sheet_id) -> tuple[int, dict[str, Any]]:
    add_breadcrumb(
        category="report",
        message=f"Extracting columns for sheet {sheet_id}",
        level="info",
    )
    sheet = Sheet.objects.get(id=sheet_id)
    char: TempestCharacter
    try:
        char = sheet.controller
        char.reconcile()
    except Exception as exc:
        capture_exception(exc)
        return {"Error": str(exc)}
    add_breadcrumb(
        category="report", message=f"Successfully loaded sheet {sheet_id} ({char})"
    )
    results: dict[str, Any] = {}
    for col, getter in _CHARACTER_COLUMNS.items():
        try:
            results[col] = getter(char)
        except Exception as exc:
            capture_exception(exc)
            results[col] = str(exc)

    return sheet_id, results


@shared_task()
def export_registrations(
    sheet_columns: Iterable[tuple[int, dict[str, Any]]], *, report_id, base_url
) -> int:
    report = models.EventReport.objects.get(pk=report_id)
    event = report.event
    all_regs = list(event.registrations.filter(canceled_date__isnull=True).all())
    stream = io.BytesIO()
    user = report.requestor
    sheet_map = {sheet: columns for (sheet, columns) in sheet_columns}

    with Workbook(stream, _WORKBOOK_OPTIONS) as wb:
        wb.set_properties(
            {
                "title": f"Registrations for {event}",
                "author": __name__,
                "manager": user.username if user else "(unknown)",
                "created": datetime.date.today(),
                "hyperlink_base": base_url,
            }
        )
        header_format = wb.add_format({"bold": True})
        _write_pc_regs(
            wb,
            header_format,
            base_url,
            sheet_map,
            (r for r in all_regs if not r.is_npc),
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
    sheet_map: dict[int, dict[str, Any]],
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
            "Link to Registration",
            "Minor?",
            "Attendance",
            "Lodging",
            "Lodging Group",
            "Character",
            "New Player?",
            "New Character?",
            "Paid?",
            "Registered",
            "Medical",
            "Emergency Contact",
            "My Guardian",
            "My Minors",
            "Details",
        ]
        + list(_CHARACTER_COLUMNS),
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

        j = 0
        sheet.write(i, j, user.username)
        j += 1
        sheet.write(i, j, str(profile))
        j += 1
        reg_url = urljoin(base_url, r.get_absolute_url())
        sheet.write_url(
            i,
            j,
            reg_url,
            string=f"Registration for {profile}",
        )
        j += 1
        sheet.write(i, j, age)
        j += 1
        sheet.write(i, j, r.get_attendance_display())
        j += 1
        sheet.write(i, j, r.get_lodging_display())
        j += 1
        sheet.write(i, j, r.lodging_group)
        j += 1
        if char:
            char_url = urljoin(base_url, char.get_absolute_url())
            sheet.write_url(i, j, char_url, string=str(char))
            j += 1
        else:
            sheet.write(i, j, "No Character")
            j += 1
        sheet.write(i, j, new_player)
        j += 1
        sheet.write(i, j, new_character)
        j += 1
        sheet.write(i, j, paid)
        j += 1
        sheet.write(i, j, reg_date)
        j += 1
        sheet.write(i, j, profile.medical)
        j += 1
        sheet.write(i, j, profile.emergency_contacts)
        j += 1
        sheet.write(i, j, profile.my_guardian)
        j += 1
        sheet.write(i, j, profile.my_minors)
        j += 1
        sheet.write(i, j, r.details)
        j += 1
        extra_columns = sheet_map.get(r.sheet_id, {"Error": "No Data"})

        for key in _CHARACTER_COLUMNS.keys():
            value = extra_columns.get(key)
            if value is not None:
                sheet.write(i, j, value)
            j += 1

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
            "Link to Registration",
            "Minor?",
            "Attendance",
            "Lodging",
            "Lodging Group",
            "New Player?",
            "New NPC?",
            "Registered",
            "Medical",
            "Emergency Contact",
            "My Guardian",
            "My Minors",
            "Details",
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

        j = 0
        sheet.write(i, j, user.username)
        j += 1
        sheet.write(i, j, str(profile))
        j += 1
        sheet.write_url(
            i,
            j,
            urljoin(base_url, r.get_absolute_url()),
            string=f"Registration for {profile}",
        )
        j += 1
        sheet.write(i, j, age)
        j += 1
        sheet.write(i, j, r.get_attendance_display())
        j += 1
        sheet.write(i, j, r.get_lodging_display())
        j += 1
        sheet.write(i, j, r.lodging_group)
        j += 1
        sheet.write(i, j, new_player)
        j += 1
        sheet.write(i, j, new_npc)
        j += 1
        sheet.write(i, j, reg_date)
        j += 1
        sheet.write(i, j, profile.medical)
        j += 1
        sheet.write(i, j, profile.emergency_contacts)
        j += 1
        sheet.write(i, j, profile.my_guardian)
        j += 1
        sheet.write(i, j, profile.my_minors)
        j += 1
        sheet.write(i, j, r.details)
        j += 1
    sheet.autofit()


def _filenameize(string: str) -> str:
    return string.translate(_FILENAME_TABLE)
