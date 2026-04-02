from django import template

register = template.Library()

@register.filter
def hide_row(counter, limit=5):
    return int(counter) > int(limit)

@register.filter
def is_equal(value, arg):
    """
    Returns True if the string representations of the two values are equal.
    Used to bypass Django's strict spacing requirements for the == operator in templates.
    """
    return str(value) == str(arg)

@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    query = context['request'].GET.copy()
    for kwarg in kwargs:
        try:
            query.pop(kwarg)
        except KeyError:
            pass
    query.update(kwargs)
    return query.urlencode()
