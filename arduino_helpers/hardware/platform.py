# -*- encoding: utf-8 -*-
from typing import Dict, Union
from path_helpers import path

from . import parse_config


def get_platform_config_by_family(arduino_home_path: Union[str, path]) -> Dict[str, path]:
    """
    Return a nested dictionary containing configuration from each platform
    supported by an Arduino installation home directory.
    """
    arduino_home_path = path(arduino_home_path).expand()
    if arduino_home_path.joinpath('hardware', 'arduino', 'cores').isdir():
        # The provided Arduino home is pre-1.5.
        raise ValueError('Arduino < 1.5 does not provide `platform.txt`.')
    else:
        hardware_family_directory = arduino_home_path.joinpath('hardware', 'arduino')
        boards_by_family = {str(d.name): parse_config(d.joinpath('platform.txt'))
                            for d in hardware_family_directory.dirs()}
    return boards_by_family
