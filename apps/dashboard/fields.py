import datetime

from django import forms


class MultiDateField(forms.CharField):
    def to_python(self, value):
        return " ".join(value.split())

    def validate(self, value):
        if not value:
            return
        dates = value.split(" ")
        for date in dates:
            try:
                datetime.datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise forms.ValidationError(
                    "Make sure all dates are correct and in YYYY-MM-DD format."
                )
        return value
