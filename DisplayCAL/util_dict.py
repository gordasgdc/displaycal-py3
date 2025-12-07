"""Temporary helper functions to ease OrderedDict removal."""

# Standard Library Imports
from __future__ import annotations

from typing import Callable


def dict_slice(
    obj: dict,
    start: None | int = None,
    stop: None | int = None,
    step: None | int = None,
) -> dict:
    """Slice the given dict.

    Args:
        obj (dict): The dictionary to work on.
        start (None | int): The start index.
        stop (None | int): The stop index.
        step (None | int): The step (currently not used).

    Returns:
        dict: The sliced dictionary.
    """
    all_keys = list(obj.keys())
    if start:
        if stop:
            return dict(
                zip(all_keys[start:stop], [obj[key] for key in all_keys[start:stop]])
            )
        return dict(zip(all_keys[start:], [obj[key] for key in all_keys[start:]]))
    if stop:
        return dict(zip(all_keys[:stop], [obj[key] for key in all_keys[:stop]]))
    start = 0
    stop = len(all_keys)
    return dict(zip(all_keys[start:stop], [obj[key] for key in all_keys[start:stop]]))


def dict_sort(obj: dict, key: None | Callable = None) -> dict:
    """Return a sorted dict.

    Args:
        obj (dict): The dictionary to work on.
        key (None | Callable): A callable to generate the key.

    Returns:
        dict: The sorted dictionary.
    """
    new_dict = {}
    for k in sorted(obj, key=key):
        new_dict[k] = obj[k]
    return new_dict


def swap_dict_keys_values(dict_in: dict) -> dict:
    """Swap dictionary keys and values.

    Args:
        dict_in (dict): The dictionary to swap.

    Returns:
        dict: The swapped dictionary.
    """
    return {v: k for k, v in dict_in.items()}
