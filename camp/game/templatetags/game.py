from __future__ import annotations

from django import template
from django.template import defaultfilters
from django.templatetags import tz

register = template.Library()


@register.filter(takes_context=True)
def chapterzone(value, chapter=None):
    if chapter and chapter.timezone:
        value = tz.do_timezone(value, chapter.timezone)
    return defaultfilters.date(value, "D M jS Y P e")
