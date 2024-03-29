# from https://stackoverflow.com/a/1112236

import re
from django import template
from django.conf import settings

numeric_test = re.compile("^\d+$")
register = template.Library()

TEMPLATE_STRING_IF_INVALID = None


# Gets an attribute of an object dynamically from a string name
def getattribute(value, arg):
    if hasattr(value, str(arg)):
        return getattr(value, arg)
    elif str(arg) in value:
        return value[arg]
    elif numeric_test.match(str(arg)) and len(value) > int(arg):
        return value[int(arg)]
    else:
        return TEMPLATE_STRING_IF_INVALID


register.filter("getattribute", getattribute)
