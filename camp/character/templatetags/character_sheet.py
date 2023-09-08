from __future__ import annotations

import itertools
from typing import Type
from typing import TypeVar

import markdown as md
import nh3
from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

from camp.engine.rules.base_engine import CharacterController
from camp.engine.rules.base_engine import PropertyController

register = template.Library()


class _StripOuterP(md.postprocessors.Postprocessor):
    def run(self, text) -> str:
        if text.startswith("<p>"):
            return text[3:-4]
        return text


class _Extension(md.extensions.Extension):
    def extendMarkdown(self, md):
        # Register instance of 'mypattern' with a priority of 175
        md.registerExtension(self)
        md.postprocessors.register(_StripOuterP(md), "stripouterp", 175)


_MD = md.Markdown(
    output="html",
    extensions=["tables", "smarty", _Extension()],
)


@register.filter()
@mark_safe
@stringfilter
def markdown(value):
    return nh3.clean(_MD.convert(value))


@register.simple_tag(takes_context=True)
def get(context: dict, expr: str, attr: str | None = None) -> int:
    """Get a value from the character sheet.

    If no controller is specified, checks the current context for a CharacterController object
    called 'controller', 'character', or failing that, just checks everything.
    """
    controller = _find_context_controller(
        context, CharacterController, ("controller", "character")
    )
    if not controller:
        raise ValueError("No controller specified and no controller found in context.")
    if attr:
        return controller.get(f"{expr}.{attr}")
    return controller.get(expr)


@register.simple_tag(takes_context=True)
def subcon(
    context: dict, expr: str, controller: CharacterController | None = None
) -> PropertyController:
    """Get a value from the character sheet.

    If no controller is specified, checks the current context for a CharacterController object
    called 'controller', 'character', or failing that, just checks everything.
    """
    if not controller:
        controller = _find_context_controller(
            context, CharacterController, ("controller", "character")
        )
    if not controller:
        raise ValueError("No controller specified and no controller found in context.")
    return controller.controller(expr)


_T = TypeVar("_T")


def _find_context_controller(
    context: template.RequestContext,
    controller_type: Type[_T],
    preferred_names: tuple[str],
) -> _T | None:
    """Find a controller of the given type in the context.

    If no controller is found, returns None.
    """
    for name in itertools.chain(preferred_names, (context.flatten().keys())):
        if controller := context.get(name):
            if isinstance(controller, controller_type):
                return controller
    return None
