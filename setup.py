# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license.
# See the NOTICE for more information.


import os
from distutils.errors import DistutilsError
import shlex
import sys
import subprocess

from setuptools import setup, find_packages
from setuptools.extension import Extension


from gunicorn import __version__


def exec_process(cmdline, silent=True, input=None, **kwargs):
    """Execute a subprocess and returns the returncode, stdout buffer and stderr buffer.
    Optionally prints stdout and stderr while running."""

    args = shlex.split(cmdline)
    try:
        sub = subprocess.Popen(args=args, stdin=None,
                stdout=None, stderr=None, **kwargs)
        stdout, stderr = sub.communicate(input=input)
        returncode = sub.returncode
        if not silent:
            sys.stdout.write(stdout)
            sys.stderr.write(stderr)
    except OSError as e:
        if e.errno == 2:
            raise DistutilsError('"%s" is not present on this system' % cmdline[0])
        else:
            raise
    return returncode




atomic_test = os.path.join(os.path.dirname(__file__), "atomic_test.c")
exts = []
if exec_process("gcc -o atomic_test %s" % atomic_test) == 0:
    if exec_process("./atomic-test") == 0:

        exts = [Extension('gunicorn._counter_atomic',
            sources=['gunicorn/_counter_atomic.c'])]



setup(
    name = 'gunicorn',
    version = __version__,

    description = 'WSGI HTTP Server for UNIX',
    long_description = file(
        os.path.join(
            os.path.dirname(__file__),
            'README.rst'
        )
    ).read(),
    author = 'Benoit Chesneau',
    author_email = 'benoitc@e-engura.com',
    license = 'MIT',
    url = 'http://gunicorn.org',

    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Other Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Topic :: Internet',
        'Topic :: Utilities',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: WSGI',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Server',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    zip_safe = False,
    packages = find_packages(exclude=['examples', 'tests']),
    include_package_data = True,

    ext_modules = [
        Extension('gunicorn._counter_atomic', sources=[
            'gunicorn/_counter_atomic.c'])
    ],

    entry_points="""

    [console_scripts]
    gunicorn=gunicorn.app.wsgiapp:run
    gunicorn_django=gunicorn.app.djangoapp:run
    gunicorn_paster=gunicorn.app.pasterapp:run

    [gunicorn.workers]
    sync=gunicorn.workers.sync:SyncWorker
    eventlet=gunicorn.workers.geventlet:EventletWorker
    gevent=gunicorn.workers.ggevent:GeventWorker
    gevent_wsgi=gunicorn.workers.ggevent:GeventPyWSGIWorker
    gevent_pywsgi=gunicorn.workers.ggevent:GeventPyWSGIWorker
    tornado=gunicorn.workers.gtornado:TornadoWorker

    [gunicorn.loggers]
    simple=gunicorn.glogging:Logger

    [paste.server_runner]
    main=gunicorn.app.pasterapp:paste_server
    """,
    test_suite = 'nose.collector',
)
