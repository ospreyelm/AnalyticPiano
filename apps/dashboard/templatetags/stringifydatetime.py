from django import template

register = template.Library()


def stringifydatetime(date):
    return date.strftime("%Y-%m-%d")


register.filter("stringifydatetime", stringifydatetime)
