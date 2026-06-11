"""Template tags for the links app. """

from django import template

from sniplink.core.lifecycle import link_display_state

register = template.Library()


@register.filter
def get_item(mapping, key):
    return mapping.get(key)


@register.filter
def link_state(link):
    return link_display_state(link)
