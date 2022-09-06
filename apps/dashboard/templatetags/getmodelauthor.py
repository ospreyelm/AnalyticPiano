from django import template

register = template.Library()


def getmodelauthor(instance, author_field_name):
    return instance[author_field_name]


register.filter("getmodelauthor", getmodelauthor)
