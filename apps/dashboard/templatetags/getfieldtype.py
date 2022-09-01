from django import template

register = template.Library()

# Takes a Django field as input, outputs a string so the template can format itself appropriately
def getfieldtype(field):
    if hasattr(field, "get_internal_type"):
        return field.get_internal_type()
    return None


register.filter("getfieldtype", getfieldtype)
