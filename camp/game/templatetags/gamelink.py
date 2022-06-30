from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def gamelink(context, game):
    """Produces a fully-qualified URL for a Game model."""
    return game.get_absolute_url(context["request"])
