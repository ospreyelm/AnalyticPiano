from datetime import datetime
from django import template
import pytz
from django.conf import settings


register = template.Library()

# Converts python datetime to a string that the date input can accept.
def stringifydatetime(date):
    if isinstance(date, datetime):
        return date.astimezone(pytz.timezone(settings.TIME_ZONE)).strftime("%Y-%m-%d")
    return ""


register.filter("stringifydatetime", stringifydatetime)
