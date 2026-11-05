from django import template

register = template.Library()


@register.filter
def get(mapping, key):
    try:
        return mapping.get(key, key)
    except AttributeError:
        return key


@register.filter
def retention(memory):
    return memory.retention()


@register.filter
def is_due(memory):
    return memory.is_due()
