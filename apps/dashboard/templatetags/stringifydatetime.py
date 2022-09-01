from datetime import datetime
from django import template

register = template.Library()


def stringifydatetime(date):
    if isinstance(date, datetime):
        return date.strftime("%Y-%m-%d")
    return ""


register.filter("stringifydatetime", stringifydatetime)
