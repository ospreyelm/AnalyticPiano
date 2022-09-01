from django import template

register = template.Library()


def getfieldtype(field):
    if hasattr(field, "get_internal_type"):
        return field.get_internal_type()
    return None


register.filter("getfieldtype", getfieldtype)
