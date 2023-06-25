from __future__ import annotations

from .. import choice_controller


class SphereBonusChoice(choice_controller.GrantChoice):
    """Choose a bonus from a magic sphere.

    This is a special case of a bonus feature chooser where the choices are linked
    to a sphere/class... _maybe_. For example, the Additional Cantrip skill lets you
    take a bonus cantrip. Simple enough, right? Wrong. If you have a casting class,
    the cantrip _must_ come from that class. If you don't have a casting class, then
    your cantrip choice can come from any casting class, but your choice of sphere
    depends on whether you have Basic Arcane and/or Basic Faith (which you must have
    at least one of to take the skill).
    """

    def _matches(self, choice: str) -> bool:
        """In addition to the normal feature match, does the rest of the filtering described above."""
        # Rule 0: The choice must match the normal feature match.
        if not super()._matches(choice):
            return False

        character = self._feature.character
        feat = character.feature_controller(choice)

        # Rule 1: The character shouldn't already have the choice.
        if character.get(choice):
            return False

        # Rule 2: The choice must come from a casting class the character has, if they have any.
        casting_classes = {claz.full_id for claz in character.classes if claz.caster}
        if casting_classes:
            # In the off chance that a cantrip/spell/whatever is listed with a cost, it should be excluded.
            # These have unique purchase rules and shouldn't be available as a choice for anything that uses
            # this controller.
            if feat.cost:
                return False
            # Otherwise, the choice must be from one of these classes.
            return feat.parent and feat.parent.full_id in casting_classes

        # Rule 3: If the character does _not_ have a casting class, the spell in question must still
        # come from a class.
        # TODO: The rules team might want to restrict this to just basic classes.
        # As is, the skills that use this controller say nothing about the type of class the spell
        # can come from.
        if not (parent := feat.parent) or not parent.feature_type == "class":
            return False

        # Rule 4: If the character does _not_ have a casting class, the choice must come from a sphere
        # they have access to via the Basic Arcane or Basic Faith skills. One of these skills is always
        # a requirement to take a skill that uses this controller, though sometimes it's implicit.
        if sphere := getattr(feat, "sphere", None):
            if sphere == "arcane" and not character.meets_requirements("basic-arcane"):
                return False
            if sphere == "divine" and not character.meets_requirements("basic-faith"):
                return False

        return True
