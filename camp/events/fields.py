from django import forms as _forms


class _DefaultModelChoiceIterator(_forms.models.ModelChoiceIterator):
    def __iter__(self):
        if self.field.empty_label is not None and self.queryset.count() != 1:
            yield ("", self.field.empty_label)
        queryset = self.queryset
        # Can't use iterator() when queryset uses prefetch_related()
        if not queryset._prefetch_related_lookups:
            queryset = queryset.iterator()
        for obj in queryset:
            yield self.choice(obj)

    def __len__(self):
        count = self.queryset.count()
        if count == 1:
            return 1
        return count + 1


class DefaultModelChoiceField(_forms.ModelChoiceField):
    iterator = _DefaultModelChoiceIterator


class _DateInput(_forms.widgets.DateInput):
    input_type = "date"


class _DateTimeInput(_forms.widgets.DateTimeInput):
    input_type = "datetime-local"


class DateField(_forms.DateField):
    widget = _DateInput


class DateTimeField(_forms.DateTimeField):
    widget = _DateTimeInput
