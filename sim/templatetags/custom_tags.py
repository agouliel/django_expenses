# https://chatgpt.com/c/69ef68dc-8920-8332-aca8-efc06fde66b2
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)
