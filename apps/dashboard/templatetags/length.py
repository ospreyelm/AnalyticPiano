from django import template

register = template.Library()


def length(iterable):
    print(iterable)
    return len(iterable)


register.filter("length", length)
