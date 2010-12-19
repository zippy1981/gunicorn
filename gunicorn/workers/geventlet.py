# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license. 
# See the NOTICE for more information.

from __future__ import with_statement


import os
import time

try:
    import eventlet
except ImportError:
    raise RuntimeError("You need eventlet installed to use this worker.")
from eventlet import hubs
from eventlet.greenio import GreenSocket

from gunicorn.workers.async import AsyncWorker

class EventletWorker(AsyncWorker):

    @classmethod
    def setup(cls):
        import eventlet
        if eventlet.version_info < (0,9,7):
            raise RuntimeError("You need eventlet >= 0.9.7")
        eventlet.monkey_patch(os=False)

    def init_process(self):
        hubs.use_hub()
        super(EventletWorker, self).init_process()

    def timeout_ctx(self):
        return eventlet.Timeout(self.cfg.keepalive, False) 

    def start_accepting(self):
        self.socket = GreenSocket(family_or_realsock=self.socket.sock)
        self.socket.setblocking(1)
        self.acceptor = eventlet.spawn(eventlet.serve, self.socket,
                self.handle, self.worker_connections)
    
    def stop_accepting(self):
        with eventlet.Timeout(self.timeout, False):
            eventlet.kill(self.acceptor, eventlet.StopServe)
