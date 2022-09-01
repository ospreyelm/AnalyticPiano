from datetime import datetime
from django import template

register = template.Library()

# Converts python datetime to a string that the date input can accept.
def stringifydatetime(date):
    if isinstance(date, datetime):
        return date.strftime("%Y-%m-%dT%m:%S")
    return ""


register.filter("stringifydatetime", stringifydatetime)
