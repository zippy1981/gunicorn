# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license. 
# See the NOTICE for more information.

from __future__ import with_statement

import os
import signal
import sys

# workaround on osx, disable kqueue
if sys.platform == "darwin":
    os.environ['EVENT_NOKQUEUE'] = "1"

try:
    import gevent
except ImportError:
    raise RuntimeError("You need gevent installed to use this worker.")
from gevent.event import Event
from gevent.pool import Pool
from gevent.server import StreamServer
from gevent import socket
from gevent import pywsgi, wsgi

import gunicorn
from gunicorn.workers.async import AsyncWorker
from gunicorn.workers.base import Worker

VERSION = "gevent/%s gunicorn/%s" % (gevent.__version__, gunicorn.__version__)

BASE_WSGI_ENV = {
    'GATEWAY_INTERFACE': 'CGI/1.1',
    'SERVER_SOFTWARE': VERSION,
    'SCRIPT_NAME': '',
    'wsgi.version': (1, 0),
    'wsgi.multithread': False,
    'wsgi.multiprocess': False,
    'wsgi.run_once': False
}

class GGeventServer(StreamServer):
    def __init__(self, listener, handle, spawn='default', worker=None):
        StreamServer.__init__(self, listener, spawn=spawn)
        self.handle_func = handle
        self.worker = worker

    def stop(self, timeout=None):
        super(GGeventServer, self).stop(timeout=timeout)

    def handle(self, sock, addr):
        self.handle_func(sock, addr)


class GeventAsyncSignal(object):
    """ common class to gevent workers. 
        We manage signals in their own greenlet, so we never block.
        
        gevent.signal doesn't work here. When too much signals come to
        the worker it fails with the error:

            [err] evsignal_cb: read: Interrupted system call
            
        Probably related to: 
        http://www.mail-archive.com/libevent-users@monkey.org/msg00385.html.
    """


    SIGNALS = map(
        lambda x: getattr(signal, "SIG%s" % x),
        "HUP QUIT INT TERM USR1 USR2 WINCH CHLD".split()
    )


    SIG_QUEUE = []
    WORKER_SIGNALS = map(
        lambda x: getattr(signal, "SIG%s" % x),
        "QUIT INT TERM".split()
    )
    SIG_NAMES = dict(
        (getattr(signal, name), name[3:].lower()) for name in dir(signal)
        if name[:3] == "SIG" and name[3] != "_"
    )

    def wakeup(self):
        self.wakeup_ev.set()

    def wait(self):
        return self.wakeup_ev.wait(self.timeout)

    def handle_signals(self):
        while self.alive: 
            sig = self.SIG_QUEUE.pop(0) if len(self.SIG_QUEUE) else None
            if sig is not None:
                signame = self.SIG_NAMES.get(sig)
                if signame in ("term", "int"):
                    handler = self.handle_exit 
                else:
                    handler = getattr(self, "handle_%s" % signame, None)
                handler()
            gevent.sleep(1.0)

    def signal(self, sig, frame):
        if len(self.SIG_QUEUE) < 5:
            self.SIG_QUEUE.append(sig)

    def init_signals(self):
        map(lambda s: signal.signal(s, signal.SIG_IGN), self.SIGNALS)
        map(lambda s: signal.signal(s, self.signal), self.WORKER_SIGNALS)
        signal.signal(signal.SIGWINCH, self.handle_winch)

class GeventWorker(GeventAsyncSignal, AsyncWorker):

    def __init__(self, *args, **kwargs):
        super(GeventWorker, self).__init__(*args, **kwargs)
        self.wakeup_ev = Event()

    @classmethod  
    def setup(cls):
        from gevent import monkey
        monkey.noisy = False
        monkey.patch_all()

    def timeout_ctx(self):
        return gevent.Timeout(self.cfg.keepalive, False)

    def start_accepting(self):
        gevent.spawn(self.handle_signals)
        self.socket.setblocking(1)
        pool = Pool(self.worker_connections)
        self.server = GGeventServer(self.socket, self.handle, spawn=pool,
                worker=self)
        self.server.start()
    
    def stop_accepting(self):
        try:
            self.server.stop(timeout=self.timeout)
        except:
            pass
        
    def handle_request(self, *args):
        try:
            super(GeventWorker, self).handle_request(*args)
        except gevent.GreenletExit:
            pass 

    def init_process(self):
        #gevent doesn't reinitialize dns for us after forking
        #here's the workaround
        gevent.core.dns_shutdown(fail_requests=1)
        gevent.core.dns_init()
        super(GeventWorker, self).init_process() 

class GeventBaseWorker(GeventAsyncSignal, Worker):
    """\
    This base class is used for the two variants of workers that use
    Gevent's two different WSGI workers. ``gevent_wsgi`` worker uses
    the libevent HTTP parser but does not support streaming response
    bodies or Keep-Alive. The ``gevent_pywsgi`` worker uses an
    alternative Gevent WSGI server that supports streaming and Keep-
    Alive but does not use the libevent HTTP parser.
    """
    server_class = None
    wsgi_handler = None

    def __init__(self, *args, **kwargs):
        super(GeventBaseWorker, self).__init__(*args, **kwargs)
        self.worker_connections = self.cfg.worker_connections
        self.wakeup_ev = Event()
        self._exit_signal = False

    @classmethod
    def setup(cls):
        from gevent import monkey
        monkey.noisy = False
        monkey.patch_all()

    def handle_exit(self, *args):
        self.alive = False
        self._exit_signal = True
        self.wakeup()

    def handle_quit(self, *args):
        self.alive = False
        self.wakeup()
        
    def run(self):
        gevent.spawn(self.handle_signals)
        self.socket.setblocking(1)

        pool = Pool(self.worker_connections)        
        self.server_class.base_env['wsgi.multiprocess'] = (self.cfg.workers > 1)
        server = self.server_class(self.socket, application=self.wsgi, 
                        spawn=pool, handler_class=self.wsgi_handler)
        server.start()

        try:
            while self.alive:
                self.notify()
                if self.ppid != os.getppid():
                    self.log.info("Parent changed, shutting down: %s" % self)
                    break
                if self.wait():
                    break
        except KeyboardInterrupt:
            pass
        
        if not self._exit_signal:
            return
        
        self.notify()
        # try to stop the connections
        try:
            server.stop(timeout=self.timeout)
        except:
            pass

    def init_process(self):
        #gevent doesn't reinitialize dns for us after forking
        #here's the workaround
        gevent.core.dns_shutdown(fail_requests=1)
        gevent.core.dns_init()
        super(GeventBaseWorker, self).init_process() 

class WSGIHandler(wsgi.WSGIHandler):
    def log_request(self, *args):
        pass

    def prepare_env(self):
        env = super(WSGIHandler, self).prepare_env()
        env['RAW_URI'] = self.request.uri
        return env
        
class WSGIServer(wsgi.WSGIServer):
    base_env = BASE_WSGI_ENV        
    
class GeventWSGIWorker(GeventBaseWorker):
    "The libevent HTTP based workers"
    server_class = WSGIServer
    wsgi_handler = WSGIHandler


class PyWSGIHandler(pywsgi.WSGIHandler):
    def log_request(self, *args):
        pass
        
    def get_environ(self):
        env = super(PyWSGIHandler, self).get_environ()
        env['gunicorn.sock'] = self.socket
        env['RAW_URI'] = self.path
        return env

class PyWSGIServer(pywsgi.WSGIServer):
    base_env = BASE_WSGI_ENV

class GeventPyWSGIWorker(GeventBaseWorker):
    "The Gevent StreamServer based workers."
    server_class = PyWSGIServer
    wsgi_handler = PyWSGIHandler
