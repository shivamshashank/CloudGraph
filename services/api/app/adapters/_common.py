"""Shared helper utilities for adapter modules."""


def get_arg(args, kwargs, index, name, default=None):
    """Retrieve an argument by position or keyword fallback."""
    if len(args) > index:
        return args[index]
    return kwargs.get(name, default)
