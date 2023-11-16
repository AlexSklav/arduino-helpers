# -*- encoding: utf-8 -*-
from collections import OrderedDict
from copy import deepcopy
from subprocess import check_output, STDOUT
import importlib.resources
import platform
import re
import sys
import os

from path_helpers import path
from typing import Any, Dict, Generator, List, IO, Union, Tuple, Optional

from .hardware import merge
from .hardware.platform import get_platform_config_by_family
from .hardware.boards import get_board_data_by_family
from .hardware.tools import (get_tools_dir_root, get_tools_dir_by_family,
                             get_compiler_dir_by_family)
from .hardware.arduino import (get_libraries_dir_by_family,
                               get_variants_dir_by_family,
                               get_firmwares_dir_by_family,
                               get_bootloaders_dir_by_family,
                               get_cores_dir_by_family, get_arduino_dir_root)


def nested_dict_iter(nested_dict: Dict[str, Any], keys: List[str] = None) -> Generator[List[str], Any, None]:
    """
    Recursively iterates through a nested dictionary and yields the keys and values.

    Args:
        nested_dict (dict): The nested dictionary to be iterated.
        keys (list, optional): List of keys from the parent dictionaries. Defaults to None.

    Yields:
        tuple: A tuple containing the list of keys and the corresponding value.
    """
    if keys is None:
        keys = []
    for k, v in nested_dict.items():
        if isinstance(v, dict):
            for nested_keys, nested_v in nested_dict_iter(v, keys=keys + [k]):
                yield nested_keys, nested_v
        else:
            yield keys + [k], v


def dump_nested_dict(nested_dict: Dict[str, Any], depth: int = 0, dump_values: bool = False, output: IO = None) -> None:
    """
    Recursively prints a nested dictionary with optional values to a given output stream.

    Args:
        nested_dict (dict): The nested dictionary to be printed.
        depth (int, optional): The current depth of nesting. Defaults to 0.
        dump_values (bool, optional): Flag to print the values. Defaults to False.
        output (file, optional): The output stream to write the output. Defaults to sys.stdout.
    """
    if output is None:
        output = sys.stdout
    for k, v in nested_dict.items():
        print(f'{" " + ("  " * depth)}{"-*"[depth & 0x01]} {k}', file=output, end='')
        if isinstance(v, dict):
            print('', file=output)
            dump_nested_dict(v, depth=depth + 1, dump_values=dump_values, output=output)
        elif dump_values:
            print(f': `{v.strip()}`', file=output)
        else:
            print('', file=output)


def resolve(config_dict: Dict[str, Any], var: str, default_value: Any = None, error_on_not_found: bool = False) -> Any:
    """
    Resolves a variable within a nested dictionary.

    Args:
        config_dict (dict): The dictionary containing configuration values.
        var (str): The variable path in dot notation.
        default_value (Any, optional): Default value to return if the variable is not found. Defaults to None.
        error_on_not_found (bool, optional): Raise an error if the variable is not found. Defaults to False.

    Returns:
        Any: The resolved value or default value.
    """
    if not re.match(r'{[a-zA-Z_][a-zA-Z_0-9]*(\.[a-zA-Z_][a-zA-Z_0-9]*)*}', var):
        raise ValueError(f'Invalid variable "{var}"')
    keys = var[1:-1].split('.')
    value = config_dict
    for k in keys:
        if error_on_not_found:
            value = value[k]
        elif value is not None:
            value = value.get(k, default_value)
    return value


def documents_directory(platform_=None) -> path:
    doc_dir = path.home() / 'Documents'
    if doc_dir.is_dir():
        return doc_dir
    else:
        raise IOError('Could not determine user `Documents` directory.')


def default_sketchbook_directory(platform_=None) -> path:
    return documents_directory(platform_).joinpath('Arduino')


def sketchbook_directory() -> path:
    return path(os.environ.get('SKETCHBOOK_HOME', default_sketchbook_directory()))


class ArduinoContext:
    def __init__(self, arduino_install_home: str):
        self.arduino_home_path = path(arduino_install_home)
        arduino_home = self.arduino_home_path
        revisions_path = arduino_home.joinpath('revisions.txt')
        # Check if the specified Arduino installation version is pre-1.5.
        self.pre_15 = not revisions_path.isfile()
        if not self.pre_15:
            # The Arduino installation version is 1.5+, which includes
            # information about the IDE run-time configuration.
            match = re.search(r'^ARDUINO \s+(?P<major>\d+) \. (?P<minor>\d+) \. (?P<micro>\d+)',
                              revisions_path.read_text(), re.VERBOSE | re.MULTILINE)
            major = int(match.group('major'))
            minor = int(match.group('minor'))
            micro = int(match.group('micro'))
            arduino_version = f'{major}_{minor}_{micro}'
            if major < 1 or (major == 1 and minor < 5):
                self.pre_15 = True
            self.runtime_config = {'runtime': {'ide': {'path': arduino_home,
                                                       'version': arduino_version}
                                               }
                                   }
        else:
            # The Arduino installation version is pre-1.5, so there is no IDE
            # run-time configuration available.
            self.runtime_config = None

    def get_arduino_dir_root(self) -> path:
        return get_arduino_dir_root(self.arduino_home_path)

    def get_tools_dir_root(self) -> path:
        return get_tools_dir_root(self.arduino_home_path)

    def get_platform_config_by_family(self) -> Dict[str, path]:
        return get_platform_config_by_family(self.arduino_home_path)

    def get_variants_dir_by_family(self) -> Dict[str, path]:
        return get_variants_dir_by_family(self.arduino_home_path)

    def get_bootloaders_dir_by_family(self) -> Dict[str, path]:
        return get_bootloaders_dir_by_family(self.arduino_home_path)

    def get_cores_dir_by_family(self) -> Dict[str, path]:
        return get_cores_dir_by_family(self.arduino_home_path)

    def get_firmwares_dir_by_family(self) -> Dict[str, path]:
        return get_firmwares_dir_by_family(self.arduino_home_path)

    def get_libraries_dir_by_family(self) -> Dict[str, path]:
        if self.pre_15:
            # Libraries were not split by family in Arduino < 1.5
            return {'avr': self.arduino_home_path.joinpath('libraries')}
        return get_libraries_dir_by_family(self.arduino_home_path)

    def get_tools_dir_by_family(self) -> Dict[str, path]:
        return get_tools_dir_by_family(self.arduino_home_path)

    def get_compiler_dir_by_family(self) -> Dict[str, path]:
        return get_compiler_dir_by_family(self.arduino_home_path)

    def get_board_data_by_family(self) -> Dict[str, Dict[str, str]]:
        return get_board_data_by_family(self.arduino_home_path)

    def get_board_names_by_family(self) -> Dict[str, List[str]]:
        return {k: list(v.keys()) for k, v in self.get_board_data_by_family().items()}


# Below is a table mapping all board names from Arduino 1.0.5 to the board/cpu
# names of Arduino 1.5+.  See `resolve_legacy_board` function below for more
# details.
LEGACY_BOARD_INFO = '''
board:cpu:name_1_0:long_name
atmegang:atmega168:atmega168:Arduino NG or older w/ ATmega168
atmegang:atmega8:atmega8:Arduino NG or older w/ ATmega8
bt:atmega168:bt:Arduino BT w/ ATmega168
bt:atmega238:bt328:Arduino BT w/ ATmega328
diecimila:atmega168:diecimila:Arduino Diecimila or Duemilanove w/ ATmega168
diecimila:atmega328:atmega328:Arduino Duemilanove w/ ATmega328
esplora::esplora:Arduino Esplora
ethernet::ethernet:Arduino Ethernet
fio::fio:Arduino Fio
leonardo::leonardo:Arduino Leonardo
lilypad:atmega168:lilypad:LilyPad Arduino w/ ATmega168
lilypad:atmega328:lilypad328:LilyPad Arduino w/ ATmega328
lilypad::LilyPadUSB:LilyPad Arduino USB
mega:atmega1280:mega:Arduino Mega (ATmega1280)
mega:atmega2560:mega2560:Arduino Mega 2560 or Mega ADK
micro::micro:Arduino Micro
mini:atmega168:mini:Arduino Mini w/ ATmega168
mini:atmega328:mini328:Arduino Mini w/ ATmega328
nano:atmega168:nano:Arduino Nano w/ ATmega168
nano:atmega328:nano328:Arduino Nano w/ ATmega328
pro:atmega168:pro:"Arduino Pro or Pro Mini (3.3V, 8 MHz) w/ ATmega168"
pro:atmega328:pro328:"Arduino Pro or Pro Mini (3.3V, 8 MHz) w/ ATmega328"
pro:atmega168:pro5v:"Arduino Pro or Pro Mini (5V, 16 MHz) w/ ATmega168"
pro:atmega328:pro5v328:"Arduino Pro or Pro Mini (5V, 16 MHz) w/ ATmega328"
robotControl::robotControl:Arduino Robot Control
robotMotor::robotMotor:Arduino Robot Motor
uno::uno:Arduino Uno
'''.strip()


def resolve_legacy_board(board_name: str) -> Union[Tuple[str, str], Tuple[None, None]]:
    """
    Return a `pandas.Series` containing the Arduino 1.5+ board name and CPU
    label corresponding to the provided pre-1.5 board name.

    Prior to Arduino version 1.5, each CPU variant of a board was treated as a
    unique board in the `boards.txt` configuration file.

    For Arduino version 1.5+, boards with different CPU variants share a common
    board name and configuration in the `boards.txt` file.  Each variant then
    overrides any necessary configuration values according to the corresponding
    `cpu` label.
    """
    for line in LEGACY_BOARD_INFO.splitlines():
        board, cpu, name_1_0, long_name = line.strip().split(':')
        if name_1_0 == board_name:
            return board, cpu
    return None, None


class Board:
    def __init__(self, arduino_context, board_name: str, cpu: Optional[str] = None):
        self.arduino_context = arduino_context
        board_configs_by_family = self.arduino_context.get_board_data_by_family()
        self.family = None
        if self.arduino_context.pre_15 and cpu is not None:
            raise ValueError('`cpu` is not valid for Arduino versions < 1.5.')
        self.cpu = cpu
        for family, board_configs in board_configs_by_family.items():
            for name in board_configs:
                if board_name == name:
                    self.family = family
        if cpu is None and self.family is None:
            board_name, cpu = resolve_legacy_board(board_name)
            self.family = 'avr'
            self.cpu = cpu
        assert (self.family is not None)
        self.name = board_name
        self.config = board_configs_by_family[self.family][board_name]
        if self.arduino_context.pre_15:
            self.platform = None
        else:
            self.platform = (self.arduino_context.get_platform_config_by_family()[self.family])

        self.cores_dir = (self.arduino_context.get_cores_dir_by_family()[self.family])
        self.libraries_dir = (self.arduino_context.get_libraries_dir_by_family()[self.family])
        self.variants_dir = (self.arduino_context.get_variants_dir_by_family()[self.family])
        self.firmwares_dir = (self.arduino_context.get_firmwares_dir_by_family()[self.family])
        self.bootloaders_dir = (self.arduino_context.get_bootloaders_dir_by_family()[self.family])
        self.combined_config = deepcopy(self.config)
        arduino_home = self.arduino_context.arduino_home_path
        self.build_config = {'build': {'arch': self.family.upper(),
                                       'system': {'path': arduino_home.joinpath('hardware', 'arduino',
                                                                                self.family.lower(), 'system')
                                                  }
                                       }
                             }
        if self.arduino_context.runtime_config is not None:
            merge(self.combined_config, self.arduino_context.runtime_config)
        if self.platform is not None:
            merge(self.combined_config, self.platform)
        merge(self.combined_config, self.build_config)
        compiler_path = self.resolve_recursive(f'{{runtime.ide.path}}/hardware/tools/{self.family.lower()}/bin')[0]
        compiler_path = path(compiler_path).expand().joinpath('')
        if path(compiler_path).isdir():
            self.combined_config.setdefault('compiler', {})['path'] = compiler_path
        if not arduino_context.pre_15 and cpu is None:
            # Check to see if multiple CPU configurations are available for the board.
            if 'menu' in self.combined_config and ('cpu' in self.combined_config['menu']):
                raise ValueError(f'Multiple CPU configurations are available '
                                 f'for the board "{board_name}" so `cpu` must be specified.')

    def resolve(self, var: List, extra_dicts: Dict = None) -> Any:
        """
        Resolve a single Arduino configuration variable, e.g., `{build.mcu}`.

        Will try to resolve CPU-specific value first, i.e.,
        `menu.cpu.<cpu>.<value>`.
        """
        if extra_dicts is None:
            extra_dicts = []
        for config_dict in [self.combined_config] + list(extra_dicts):
            key = var[1:-1]
            # First, try to resolve CPU-specific value.
            value = resolve(config_dict, f'{{menu.cpu.{self.cpu}.{key}}}')
            if value is not None:
                return value
            else:
                # Try to resolve non-CPU specific value.
                value = resolve(config_dict, f'{{{key}}}')
                if value is not None:
                    return value

    def resolve_arduino_vars(self, pattern: str, extra_dicts: Optional[Dict] = None) -> Tuple[str, List]:
        """
        Resolve Arduino configuration variables in input pattern, e.g.:

            'some string {build.mcu} {build.board} ...'
        """
        var_map = {}
        for var in re.findall(r'{.*?}', pattern):
            try:
                value = self.resolve(var, extra_dicts)
            except ValueError:
                value = None
            var_map[var] = value
        cmd = pattern
        resolved = []
        unresolved = []

        for var, value in var_map.items():
            if not isinstance(value, (str,)):
                unresolved.append(var)
            else:
                try:
                    cmd = cmd.replace(var, value)
                    resolved.append((var, value))
                except Exception:
                    print(var, value)
                    raise
        return cmd, unresolved

    def resolve_recursive(self, config_str: str, extra_dicts: Optional[Dict] = None) -> Tuple[str, List]:
        cre_var = re.compile(r'({[a-zA-Z_]+(\.[a-zA-Z_]+)*})')

        resolved_str, unresolved = self.resolve_arduino_vars(config_str, extra_dicts)

        most_recent_unresolved_matches = None
        unresolved_matches = cre_var.findall(resolved_str)

        # Since Arduino configuration values may contain `{...}`-style
        # replacement strings, retry resolving variables until all remaining
        # replacement strings cannot be resolved using the available configuration data.
        while resolved_str is None or most_recent_unresolved_matches != unresolved_matches:
            resolved_str, unresolved = self.resolve_arduino_vars(resolved_str, extra_dicts)
            most_recent_unresolved_matches = unresolved_matches
            unresolved_matches = cre_var.findall(resolved_str)
        # Without the replacement below, some strings have extraneous escaped
        # quotes, _e.g._,
        #   \'-DUSB_MANUFACTURER="Unknown"\' \'-DUSB_PRODUCT="Arduino Due"\'
        resolved_str = resolved_str.replace("\'", '')
        return resolved_str, unresolved

    @property
    def mcu(self) -> str:
        return self.config['build']['mcu']

    def get_core_dir(self) -> path:
        core = self.combined_config['build']['core']
        return self.arduino_context.get_cores_dir_by_family()[self.family].joinpath(core)

    def get_libraries_dir(self) -> path:
        return self.arduino_context.get_libraries_dir_by_family()[self.family]

    def get_variants_dir(self) -> path:
        return self.arduino_context.get_variants_dir_by_family()[self.family]

    def __getitem__(self, string: str) -> Tuple[str, List]:
        """
        Resolve an Arduino configuration string, e.g.:

            '... {build.mcu} {build.arch} ...'

        Will try to resolve CPU-specific value first, i.e.,
        `{menu.cpu.<cpu>.<value>}`.
        """
        return self.resolve_recursive(string)


class Uploader:
    def __init__(self, board_context):
        self.board_context = board_context
        upload_tool = self.board_context.config['upload'].get('tool', None)
        if upload_tool is None:
            self.upload_tool = 'avrdude'
        else:
            self.upload_tool = upload_tool
        self.tools_dir = self.board_context.arduino_context.get_tools_dir_by_family()[self.board_context.family]
        self.bin_dir = self.board_context.arduino_context.get_compiler_dir_by_family()[self.board_context.family]

    @property
    def flags(self) -> Dict:
        return OrderedDict([('-C', self.conf_path),
                            ('-c', self.protocol),
                            ('-p', self.board_context.mcu),
                            ('-b', self.speed)
                            ])

    @property
    def arduino_extra_flags(self) -> Dict:
        # Disable auto erase for flash memory.
        # __NB__ Enabled by default by Arduino IDE.
        return OrderedDict([('-D', None)])

    @property
    def protocol(self) -> str:
        return self.board_context.config['upload']['protocol']

    @property
    def speed(self) -> int:
        return int(self.board_context.config['upload']['speed'])

    @property
    def maximum_size(self) -> int:
        return int(self.board_context.config['upload']['maximum_size'])

    def bin(self) -> str:
        tool = self.bin_dir.joinpath(self.upload_tool)
        if platform.system() == 'Windows':
            return tool + '.exe'
        else:
            return tool

    @property
    def conf_path(self) -> path:
        if self.upload_tool == 'avrdude':
            conf_path = self.tools_dir.joinpath('etc', 'avrdude.conf')
            if not conf_path.isfile():
                conf_path = self.board_context.arduino_context.get_tools_dir_root().joinpath('avrdude.conf')
            if not conf_path.isfile():
                raise IOError('`avrdude.conf` not found.')
            return conf_path

    def upload(self, bitstream_file: str, port: str, verify: bool = True) -> bytes:
        if self.board_context.family not in ('avr',):
            raise NotImplementedError(f'Upload not supported for board family `{self.board_context.family}`.')
        flags = self.flags
        flags['-D'] = None
        flags['-P'] = port
        if not verify:
            flags['-V'] = None
        flags['-U'] = f'flash:w:{path(bitstream_file).abspath()}:i'
        return check_output(f'"{self.bin()}" ' + ' '.join([f'{flag} "{val}"' for flag, val in flags.items()]),
                            stderr=STDOUT, shell=True)


class Compiler:
    def __init__(self, board_context):
        self.board_context = board_context
        self._bin_dir = self.board_context.arduino_context.get_compiler_dir_by_family()[self.board_context.family]
        bin_prefix = {'avr': 'avr-',
                      'sam': 'arm-none-eabi-'}[self.board_context.family]
        self._bin_prefix = self.bin_dir.joinpath(bin_prefix)

    @property
    def bin_prefix(self) -> path:
        return self._bin_prefix

    @property
    def bin_dir(self) -> path:
        return self._bin_dir


def auto_context() -> ArduinoContext:
    if platform.system() == 'Linux':
        context_path = '/usr/share/arduino'
    else:
        context_path = importlib.resources.files(__name__).joinpath('lib', 'arduino-1.0.5-base')
    return ArduinoContext(context_path)
