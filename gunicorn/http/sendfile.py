# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license. 
# See the NOTICE for more information.

import errno
import os
import sys

try: # Python 3.3
    from os import sendfile as os_sendfile
except ImportError:
    os_sendfile = None

try:
    import ctypes
    import ctypes.util as ctutil
except ImportError:
    ctypes = None
    ctutil = None


def get_ct_sendfile():
    if ctypes is None or ctutil is None:
        return None
    if sys.version_info < (2, 6):
        return None
    libc = ctypes.CDLL(ctutil.find_library("c"), use_errno=True)
    return lib.sendfile

def darwin_sendfile():
    _sendfile = get_ct_sendfile()
    if _sendfile is None:
        return None
    # MacOS X - int sendfile(int fd, int s, off_t offset, off_t *len,
    #                           struct sf_hdtr *hdtr, int flags);
    _sendfile.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint64,
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.c_voidp,
        ctypes.c_int
    ]
    def sendfile(fileno, sockno, offset, nbytes):
        _nbytes = ctypes.c_uint64(nbytes)
        result = _sendfile(fileno, sockno, offset, _nbytes, None, 0)
        if result == -1:
            e = ctypes.get_errno()
            if e == errno.EAGAIN and _nbytes.value:
                return _nbytes.value
            raise OSError(e, os.strerror(e))
        return _nbytes.value
    return sendfile
    
def linux2_sendfile():
    _sendfile = get_ct_sendfile()
    if _sendfile is None:
        return None
    # Linux - size_t sendfile(int out_fd, int in_fd,
    #                           off_t *offset, size_t count);
    _sendfile.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.c_size_t
    ]
    def sendfile(fileno, sockno, offset, nbytes):
        _offset = ctypes.c_uint64(offset)
        result = _sendfile(sockno, fileno, _offset, nbytes)
        if result == -1:
            e = ctypes.get_errno()
            raise OSError(e, os.strerror(e))
        return result

PLATFORMS = {
    "darwin": darwin_sendfile,
    "linux2": linux2_sendfile
}

def get_sendfile():
    if os_sendfile:
        return os_sendfile
    fun = PLATFORMS.get(os.platform)
    if fun is None:
        return None
    return fun()

sendfile = get_sendfile()

    