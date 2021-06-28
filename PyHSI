#!/usr/bin/env python3

import argparse
import os
import sys

# from pyhsi.GUI import PyHSI
from pyhsi.gui.main import PyHSI


def main(args):
    parser = argparse.ArgumentParser(description="Launch PyHSI GUI")
    parser.add_argument(
        '-d', '--debug', action='store_true',
        help="print debug information to console"
    )
    parser.add_argument(
        '--hidpi', action='store_true',
        help="scale icons up for hi-DPI displays"
    )
    parser.add_argument(
        '-c', '--config', default=None, type=argparse.FileType('r'),
        help="configuration file to load"
    )
    parser.add_argument(
        'files', nargs='*', default=None, type=argparse.FileType('r'),
        help="ENVI file to open in viewer"
    )
    opts = parser.parse_args(args)
    if opts.config is not None:
        opts.config.close()
        config = opts.config.name
        if not config.endswith('.phc'):
            sys.stderr.write("Configuration file should be of type *.phc\n")
            sys.exit(1)
    else:
        config = None
    start_files = []
    for f in opts.files:
        f.close()
        start_files.append(f.name)
        if not f.name.endswith('.hdr'):
            sys.stderr.write("Can currently only load files of type *.hdr\n")
            sys.exit(1)
    app = PyHSI(
        debug=opts.debug,
        config=config,
        start_files=start_files,
        hidpi=opts.hidpi
    )
    app.run()


if __name__ == '__main__':
    main(sys.argv[1:])
