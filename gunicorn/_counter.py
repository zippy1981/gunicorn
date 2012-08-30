# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license.
# See the NOTICE for more information.
#
# This module handle a simple counter that could be shared between the
# arbiter and the the worker.


try:
    import ctypes
except MemoryError:
    raise ImportError


try:
    _path = os.path.dirname(os.path.abspath(__file__))
    _atomic_counter = ctypes.cdll.LoadLibrary(os.path.join(_path,
        "_counter_atomic.so"))
    _atomic_int_add = _atomic_counter.atomic_int_add
    _atomic_int_sub = _atomic_counter.atomic_int_sub


    # declare types
    restype = ctypes.c_int
    argtypes = [ctypes.c_void_p, ctypes.c_ulong]

    _atomic_int_add.restype = restype
    _atomic_int_add.argtypes = argtypes
    _atomic_int_sub.restype = restype
    _atomic_int_sub.argtypes = argtypes

    def incr(va, vb):
        if isinstance(va, int):
            va = ctypes.c_int(va)

        if isinstance(vb, int):
            vb = ctypes.c_ulong(vb)
        return _atomic_int_add(ctypes.pointer(va), vb)

    def descr(va, vb):
        if isinstance(va, int):
            va = ctypes.c_int(va)

        if isinstance(vb, int):
            vb = ctypes.c_ulong(vb)

        return _atomic_int_sub(ctypes.pointer(va), vb)


except:
    def incr(va, vb):
        if isinstance(va, int):
                va = ctypes.c_int(va)

            if isinstance(vb, int):
                vb = ctypes.c_ulong(vb)

        with threading.Lock():
            return va + vb

    def descr(va, vb):
        if isinstance(va, int):
            va = ctypes.c_int(va)

        if isinstance(vb, int):
            vb = ctypes.c_ulong(vb)

        with threading.Lock():
            return va - vb


class _CTypesCounter(object):

    def __init__(self, initial_value=0):
        self._mmap = mmap.mmap(-1, mmap.PAGESIZE)
        self._count = ctypes.c_int.from_buffer(self._mmap)

        # init map
        self._count.value = initial_value

    def incr(self, i=1):
        incr(self._count, i)

    def decr(self, i=1):
        descr(self._count, i)

    def set(self, v):
        self._count.value = v

    def get(self):
        return self._count.value

    def close(self):
        self._mmap.close()

if IS_PYPY:
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
else:
    Counter = _CTypesCounter

