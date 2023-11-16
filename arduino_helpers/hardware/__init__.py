# -*- encoding: utf-8 -*-
import logging
from itertools import groupby
from typing import Any, Dict, List, Tuple, Union, Optional

from path_helpers import path

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def traverse(data: List[Union[Tuple[str, Any], Any]]) -> Dict[str, Any]:
    """
    Recursively traverse entries to return Arduino-config values in a nested-dictionary.

    Args:
        data (list): List of entries containing keys and values.

    Returns:
        dict: A nested dictionary with Arduino-config values.
    """
    results = {}
    if data[0][0]:
        for key, group in groupby([d for d in data if d[0]], lambda x: x[0][0]):
            group_data = list(group)
            results[key] = traverse([(item[0][1:], item[1]) for item in group_data])
        return results
    else:
        return data[0][1]


def parse_config(config_path: Union[str, path]) -> Dict[str, Any]:
    """
    Return a nested dictionary containing configuration from an
    Arduino-formatted configuration file _(e.g., `platform.txt`,
    `boards.txt`)_.
    """
    config_data = sorted([line.strip() for line in path(config_path).lines()
                          if line.strip() and not line.startswith('#')])
    config_cleaned_data = []
    for d in config_data:
        if '=' in d:
            split_position = d.index('=')
            key = d[:split_position].split('.')
            value = d[split_position + 1:]
            config_cleaned_data.append([key, value])
    return traverse(config_cleaned_data)


def merge(a: dict, b: dict, path_: Optional[List] = None) -> Dict[str, Any]:
    """merges b into a"""
    if path_ is None:
        path_ = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], path_ + [str(key)])
            elif a[key] == b[key]:
                pass  # same leaf value
            else:
                # raise Exception(f'Conflict at {".".join(path + [str(key)])}')
                logger.warning(f"Conflict at {'.'.join(path_ + [str(key)])}")
        else:
            a[key] = b[key]
    return a
