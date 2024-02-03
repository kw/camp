from django import forms

from camp.game.fields import DateField

from . import models


class MembershipForm(forms.ModelForm):
    birthdate = DateField(help_text=models.Membership.birthdate.field.help_text)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Once you've set your birthdate, you can't change it without intervention.
        if self.instance.birthdate is not None:
            bday: forms.Field = self.fields["birthdate"]
            bday.disabled = True

    class Meta:
        model = models.Membership
        exclude = ["joined", "game", "user"]
