# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license. 
# See the NOTICE for more information.

import logging
import os
import re
import sys
from urllib import unquote

from gunicorn import SERVER_SOFTWARE
from gunicorn.http.parser import Parser
from gunicorn.http.message import Request


import gunicorn.util as util

NORMALIZE_SPACE = re.compile(r'(?:\r\n)?[ \t]+')

log = logging.getLogger(__name__)

class WSGIRequest(Request):

    def __init__(self, unreader):
        self.server = None
        self.expect_continue = False 
        self.forward = None
        self.url_scheme = "http"
        self.script_name = os.environ.get("SCRIPT_NAME", "")
        self.environ = {}
        super(WSGIRequest, self).__init__(unreader)

    def handle_header(self, name, value):
        if name == "EXPECT":
            if value.lower() == "100-continue":
                self.expect_continue = True

        elif name == "X-FORWARDED-FOR":
            self.forward = hdr_value
        elif name == "X-FORWARDED-PROTOCOL" and value.lower() == "ssl":
            self.url_scheme = "https"
        elif name == "X-FORWARDED-SSL" and value.lower() == "on":
            self.url_scheme = "https"
        elif name == "HOST":
            self.server = value
        elif name == "SCRIPT_NAME":
            self.script_name = value
        elif name == "CONTENT-TYPE":
            self.environ['CONTENT_TYPE'] = value
            return
        elif name == "CONTENT-LENGTH":
            self.environ['CONTENT_LENGTH'] = value
            return
        
        key = 'HTTP_' + name.replace('-', '_')
        self.environ[key] = value

class WSGIRequestParser(Parser):
    def __init__(self, *args, **kwargs):
        super(WSGIRequestParser, self).__init__(WSGIRequest, *args, 
                **kwargs)

def create(req, sock, client, server, cfg):
    if req.expect_continue:
        sock.send("HTTP/1.1 100 Continue\r\n\r\n")

    resp = Response(req, sock)

    environ = {
        "wsgi.input": req.body,
        "wsgi.errors": sys.stderr,
        "wsgi.version": (1, 0),
        "wsgi.multithread": False,
        "wsgi.multiprocess": (cfg.workers > 1),
        "wsgi.run_once": False,
        "gunicorn.socket": sock,
        "SERVER_SOFTWARE": SERVER_SOFTWARE,
        "REQUEST_METHOD": req.method,
        "QUERY_STRING": req.query,
        "RAW_URI": req.uri,
        "SERVER_PROTOCOL": "HTTP/%s" % ".".join(map(str, req.version)),
        "CONTENT_TYPE": "",
        "CONTENT_LENGTH": ""
    }
    
    # authors should be aware that REMOTE_HOST and REMOTE_ADDR
    # may not qualify the remote addr:
    # http://www.ietf.org/rfc/rfc3875
    client = client or "127.0.0.1"
    forward = req.forward or client

    server = req.server or server
   
    environ.update(req.environ)
    environ['wsgi.url_scheme'] = req.url_scheme
        
    if isinstance(forward, basestring):
        # we only took the last one
        # http://en.wikipedia.org/wiki/X-Forwarded-For
        if forward.find(",") >= 0:
            forward = forward.rsplit(",", 1)[1].strip()
        remote = forward.split(":")
        if len(remote) < 2:
            remote.append('80')
    else:
        remote = forward 

    environ['REMOTE_ADDR'] = remote[0]
    environ['REMOTE_PORT'] = str(remote[1])

    if isinstance(server, basestring):
        server =  server.split(":")
        if len(server) == 1:
            if req.url_scheme == "http":
                server.append("80")
            elif res.url_scheme == "https":
                server.append("443")
            else:
                server.append('')
    environ['SERVER_NAME'] = server[0]
    environ['SERVER_PORT'] = server[1]

    path_info = req.path
    if req.script_name:
        path_info = path_info.split(req.script_name, 1)[1]
    environ['PATH_INFO'] = unquote(path_info)
    environ['SCRIPT_NAME'] = req.script_name

    return resp, environ

class Response(object):

    def __init__(self, req, sock):
        self.req = req
        self.sock = sock
        self.version = SERVER_SOFTWARE
        self.status = None
        self.chunked = False
        self.should_close = req.should_close()
        self.headers = []
        self.headers_sent = False

    def force_close(self):
        self.should_close = True

    def start_response(self, status, headers, exc_info=None):
        if exc_info:
            try:
                if self.status and self.headers_sent:
                    raise exc_info[0], exc_info[1], exc_info[2]
            finally:
                exc_info = None
        elif self.status is not None:
            raise AssertionError("Response headers already set!")

        self.status = status
        self.process_headers(headers)
        return self.write

    def process_headers(self, headers):
        for name, value in headers:
            assert isinstance(name, basestring), "%r is not a string" % name
            if util.is_hoppish(name):
                lname = name.lower().strip()
                if lname == "transfer-encoding":
                    if value.lower().strip() == "chunked":
                        self.chunked = True
                elif lname == "connection":
                    # handle websocket
                    if value.lower().strip() != "upgrade":
                        continue
                else:
                    # ignore hopbyhop headers
                    continue
            self.headers.append((name.strip(), str(value).strip()))

    def default_headers(self):
        connection = "keep-alive"
        if self.should_close:
            connection = "close"

        return [
            "HTTP/1.1 %s\r\n" % self.status,
            "Server: %s\r\n" % self.version,
            "Date: %s\r\n" % util.http_date(),
            "Connection: %s\r\n" % connection
        ]

    def send_headers(self):
        if self.headers_sent:
            return
        tosend = self.default_headers()
        tosend.extend(["%s: %s\r\n" % (n, v) for n, v in self.headers])
        util.write(self.sock, "%s\r\n" % "".join(tosend))
        self.headers_sent = True

    def write(self, arg):
        self.send_headers()
        assert isinstance(arg, basestring), "%r is not a string." % arg
        util.write(self.sock, arg, self.chunked)

    def close(self):
        if not self.headers_sent:
            self.send_headers()
        if self.chunked:
            util.write_chunk(self.sock, "")
