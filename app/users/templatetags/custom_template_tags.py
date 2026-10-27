from django import template

register = template.Library()


@register.simple_tag
def setvar(val=None):
    return val


@register.filter
def getfield(value, arg):
    """Gets an attribute of an object dynamically from a string name"""
    # import pdb; pdb.set_trace()
    if hasattr(value, "fields"):
        fields = value.fields
        if str(arg) in fields:
            return str(fields[str(arg)])


@register.filter
def inlist(value, list):
    return value in list.split(",")
