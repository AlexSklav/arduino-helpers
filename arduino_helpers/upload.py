# -*- encoding: utf-8 -*-
from typing import Optional, List
from serial_device import get_serial_ports
from .context import (auto_context, Board, Uploader, ArduinoContext)


def upload_firmware(firmware_path: str, board_name: str, port: str = None,
                    arduino_install_home: str = None, **kwargs) -> bytes:
    """
    Upload the specified firmware file to the specified board.
    """
    if arduino_install_home is None:
        context = auto_context()
    else:
        context = ArduinoContext(arduino_install_home)
    board = Board(context, board_name)
    uploader = Uploader(board)
    available_ports = list(get_serial_ports())
    if port is None:
        # No serial port was specified.
        if len(available_ports) == 1:
            # There is only one serial port available, so select it automatically.
            port = available_ports[0]
        else:
            raise IOError(f'No serial port was specified. '
                          f'Please select one of the following ports: {available_ports}')
    return uploader.upload(firmware_path, port, **kwargs)


def upload(board_name: str, get_firmware: callable, port: str = None,
           arduino_install_home: str = None, **kwargs) -> bytes:
    """
    Upload the first firmware that matches the specified board type.
    """
    firmware_path = get_firmware(board_name)
    return upload_firmware(firmware_path, board_name, port, arduino_install_home, **kwargs)


def get_arg_parser():
    from argparse import ArgumentParser
    from path_helpers import path

    parser = ArgumentParser(description='Upload firmware to Arduino board.')
    parser.add_argument('board_name', type=path, default=None)
    parser.add_argument('-p', '--port', default=None)
    parser.add_argument('-V', '--skip-verify', action='store_true')
    parser.add_argument('--arduino-install-home', type=path, default=None)
    return parser


def parse_args(args: Optional[List[str]] = None):
    """Parses arguments, returns (options, args)."""
    import sys

    if args is None:
        args = sys.argv

    parser = get_arg_parser()

    args = parser.parse_args()
    return args
