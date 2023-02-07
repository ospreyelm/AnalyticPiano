from django import template

register = template.Library()


def length(iterable):
    return len(iterable)


register.filter("length", length)
