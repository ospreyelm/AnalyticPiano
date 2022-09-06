from django import template

register = template.Library()

# Returns readable name from inputted field. Originally did some complex logic to pull from verbose_name but now just returns the label. Might not be necessary anymore.
def getfieldname(field):
    return field.label


register.filter("getfieldname", getfieldname)
