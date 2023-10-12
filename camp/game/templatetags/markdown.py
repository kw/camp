from __future__ import annotations

import markdown as md
import nh3
from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

register = template.Library()


class _Extension(md.extensions.Extension):
    def extendMarkdown(self, md):
        md.registerExtension(self)


_MD = md.Markdown(
    output="html",
    extensions=["tables", "smarty", _Extension()],
)


@register.filter()
@mark_safe
@stringfilter
def markdown(value):
    return nh3.clean(_MD.convert(value))
