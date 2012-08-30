# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license.
# See the NOTICE for more information.
#
# This module handle a simple counter that could be shared between the
# arbiter and the the worker.



import errno
import mmap
import struct

from gunicorn.util import IS_PYPY


try:
    from gunicorn._counter import _Counter
except ImportError:
    _Counter = None


if not _Counter:
    import threading

    class Counter(object):

        def __init__(self, initial_value=0):
            self._mmap = mmap.mmap(-1, mmap.PAGESIZE)
            self._count = 0
            self._commit(self._count)

        def _commit(self, val):

            with threading.Lock():
                s = struct.pack('i', val)
                self._mmap.seek(0)
                self._mmap.write(s)


        def incr(self, i=1):
            with threading.Lock():
                self._count += i
                self._commit(self._count)

        def decr(self, i=1):
            with threading.Lock():
                self._count -= i
                self._commit(self._count)

        def set(self, v):
            with threading.Lock():
                self._count = v
                self._commit(self._count)

        def get(self):
            self._mmap.seek(0)
            i, = struct.unpack('i', self._mmap[:4])
            return i

        def close(self):
            self._mmap.close()
else:
    Counter = _Counter
