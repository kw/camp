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
    extensions=["tables", "smarty", "attr_list"],
)


@register.filter()
@mark_safe
@stringfilter
def markdown(value, arg=None):
    if arg:
        attr_values = {
            "p": {"class": arg},
        }
    else:
        attr_values = None
    return nh3.clean(_MD.convert(value), set_tag_attribute_values=attr_values)
