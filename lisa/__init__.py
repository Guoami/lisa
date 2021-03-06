#! /usr/bin/env python3

import warnings
import os
import sys


from lisa.version import __version__

# Raise an exception when a deprecated API is used from within a lisa.*
# submodule. This ensures that we don't use any deprecated APIs internally, so
# they are only kept for external backward compatibility purposes.
warnings.filterwarnings(
    action='error',
    category=DeprecationWarning,
    module=r'{}\..*'.format(__name__),
)

# When the deprecated APIs are used from __main__ (script or notebook), always
# show the warning
warnings.filterwarnings(
    action='always',
    category=DeprecationWarning,
    module=r'__main__',
)

# Prevent matplotlib from trying to connect to X11 server, for headless testing.
# Must be done before importing matplotlib.pyplot or pylab
try:
    import matplotlib
except ImportError:
    pass
else:
    if not os.getenv('DISPLAY'):
        matplotlib.use('Agg')

if sys.version_info < (3, 6):
    warnings.warn(
        'Python 3.6 will soon be required to run LISA, please upgrade from {} to any version higher than 3.6'.format(
            '.'.join(
                map(str, tuple(sys.version_info)[:3])
            ),
        ),
        DeprecationWarning,
    )

# vim :set tabstop=4 shiftwidth=4 textwidth=80 expandtab
