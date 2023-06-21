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


@register.filter()
@mark_safe
@stringfilter
def markdown(value):
    return nh3.clean(md.markdown(value, extensions=["tables", "smarty"]))


@register.simple_tag(takes_context=True)
def get(context: dict, expr: str, controller: CharacterController | None = None) -> int:
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
