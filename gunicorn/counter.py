# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license.
# See the NOTICE for more information.

try:
    import ctypes
except MemoryError:
    ctypes = None
except ImportError:
    ctypes = None

import errno
import mmap
import struct

from gunicorn.workers.workertmp import WorkerTmp
from gunicorn.util import IS_PYPY

class _CTypesCounter(object):

    def __init__(self, initial_value=0):
        self._mmap = mmap.mmap(-1, mmap.PAGESIZE)
        self._count = ctypes.c_int.from_buffer(self._mmap)

        # init map
        self._count.value = initial_value

    def incr(self, i=1):
        self._count.value += i

    def decr(self, i=1):
        self._count.value -= i

    def set(self, v):
        self._count.value = v

    def get(self):
        return self._count.value

    def close(self):
        self._mmap.close()


class _SimpleCounter(object):

    def __init__(self, initial_value=0):
        self._mmap = mmap.mmap(-1, mmap.PAGESIZE)
        self._count = 0

        self._commit()

    def _commit(self):
        self._mmap.seek(0)
        s = struct.pack('i', self._count)
        self._mmap.write(s)


    def incr(self, i=1):
        self._count += i
        self._commit()

    def decr(self, i=1):
        self._count -= i
        self._commit()

    def set(self, v):
        self._count = v
        self._commit()

    def get(self):
        self._mmap.seek(0)
        i, = struct.unpack('i', self._mmap[:4])
        return i

    def close(self):
        self._mmap.close()



if IS_PYPY and ctypes:
    _libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    _mmap = _libc.mmap
    _munmap = _libc.munmap

    # declare types
    _mmap.restype = ctypes.c_void_p
    _mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    _munmap.restype = ctypes.c_int
    _munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]


    class Counter(_CTypesCounter):

        def __init__(self, initial_value=0):
            self._mmap = _mmap(None,
                               mmap.PAGESIZE,
                               mmap.PROT_READ | mmap.PROT_WRITE,
                               mmap.MAP_SHARED | mmap.MAP_ANON,
                               -1,
                               0)

            if self._mmap == -1:
                c = ctypes.geterrno()
                raise OSError(e, os.strerror(e))

            self._count = ctypes.c_int.from_address(self._mmap)

            # init map
            self._count.value = initial_value


        def close(self):
            res = _munmap(self._mmap, mmap.PAGESIZE)
            if res == -1:
                c = ctypes.geterrno()
                raise OSError(e, os.strerror(e))

elif ctypes:
    Counter = _CTypesCounter
else:
    Counter = _SimpleCounter
