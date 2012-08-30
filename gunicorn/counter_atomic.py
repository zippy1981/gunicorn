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
    ctypes = None
except ImportError:
    ctypes = None
import os

import threading

if ctypes:
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
        raise
        pass
else:
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





