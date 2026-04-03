from datetime import datetime
from zoneinfo import ZoneInfo
from django import template
from django.conf import settings


register = template.Library()

# Converts python datetime to a string that the date input can accept.
def stringifydatetime(date):
    if isinstance(date, datetime):
        return date.astimezone(ZoneInfo(settings.TIME_ZONE)).strftime("%Y-%m-%d") # TODO: check this
    return ""


register.filter("stringifydatetime", stringifydatetime)
