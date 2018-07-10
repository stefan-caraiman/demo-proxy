"""Web Server Dispach Services."""
from __future__ import print_function

import uuid
import json
import logging
import time
import threading

from six.moves import http_client
from six.moves import queue
import gunicorn.app.base
from gunicorn.six import iteritems
import requests

from demo_proxy.common import worker as demo_proxy_worker


LOG = logging.getLogger(__name__)
LOG.addHandler(logging.StreamHandler())


class _HTTPHeaders(object):
    """Container for HTTP Headers."""

    def __init__(self):
        self._items = {}

    def __getitem__(self, key):
        """Get specific item form row"""
        return self._items[key]

    def __setitem__(self, key, value):
        """Set specific item in specific row"""
        self._items[key] = value

    def __delitem__(self, key):
        """Delete specifc item from row"""
        del self._items[key]

    def raw_data(self):
        """Dump the raw content of the current object."""
        return self._items.copy()

    def to_json(self):
        """Dump the headers as JSON file."""
        return json.dumps(self._items)

    @classmethod
    def from_json(cls, data):
        """Dump the current object as JSON file."""
        headers = cls()
        raw_headers = json.load(data)
        for key in raw_headers:
            headers[key.title()] = raw_headers[key]
        return headers

    @classmethod
    def from_environ(cls, environ):
        """Create a new object from the Gunicorn environ."""
        headers = cls()
        for key in environ:
            if key.startswith("HTTP_"):
                header = key.replace("HTTP_", "").replace("_", "-")
                headers[header.title()] = environ[key]
        return headers

    @classmethod
    def from_response(cls, http_response):
        """Create a new object from the requests.response."""
        headers = cls()
        for key in http_response.headers:
            headers[key] = http_response.headers[key]
        return headers


class _HTTPObject(object):
    """Simple wrapper over the HTTP request/response."""

    def __init__(self, **fields):
        self._data = {}
        white_list = ('method', 'uri', 'path', 'query',
                      'headers', 'body', 'uuid')

        for key in white_list:
            self._data[key] = fields[key] if key in fields else None
        self._data['uuid'] = self._data['uuid'] or str(uuid.uuid4())

    @property
    def uuid(self):
        """Get the UUID for the current object."""
        return self._data.get('uuid')

    @property
    def headers(self):
        """Get the request headers."""
        headers = self._data.get('headers')
        return headers if headers else {}

    @property
    def body(self):
        """Get the request body."""
        return self._data.get('body')

    @property
    def method(self):
        """Return the HTTP method used."""
        return self._data.get('method')

    @property
    def uri(self):
        """Return the raw URI."""
        return self._data.get('uri')

    @property
    def query(self):
        """Return the query string."""
        return self._data.get('query')

    @property
    def path(self):
        """Return the request path."""
        return self._data.get('path')

    def to_json(self):
        """Dump object as JSON file."""
        data = self._data.copy()
        if isinstance(data['headers'], _HTTPHeaders):
            data['headers'] = data['headers'].raw_data()
        return json.dumps(data)

    @classmethod
    def from_json(cls, data):
        """Create a new object from JSON file."""
        arguments = json.loads(data.decode())
        return cls(**arguments)


class _HTTPRequest(_HTTPObject):
    """Simple wrapper over HTTP request."""

    @classmethod
    def from_environ(cls, environ):
        """Create a new object from Gunicorn environ."""
        arguments = {
            'headers': _HTTPHeaders.from_environ(environ),
            'method': environ.get("REQUEST_METHOD"),
            'uri': environ.get("RAW_URI"),
            'path': environ.get("PATH_INFO"),
            'query': environ.get("QUERY_STRING"),
        }
        return cls(**arguments)


class _HTTPResponse(_HTTPObject):
    """Simple wraper over the HTTP response."""

    def __init__(self, status="200 OK", **fields):
        super(_HTTPResponse, self).__init__(**fields)
        self._data['status'] = status

    @property
    def status(self):
        """Return the HTTP Response status."""
        return self._data.get("status")


class DemoProxy(gunicorn.app.base.BaseApplication):
    """DemoProxy standalone application."""

    def __init__(self, tasks_queue, delay=0.2, timeout=8, **gunicorn_options):
        self._options = gunicorn_options
        self._queue = tasks_queue
        self._timeout = timeout
        self._delay = delay
        super(DemoProxy, self).__init__()

    def _dispatch(self, environ, start_response):
        request = _HTTPRequest.from_environ(environ)
        # Overwrite the User Agent in order to avoid issues
        request.headers["User-Agent"] = "DemoProxy"
        # Overwrite the Accept header in order to keep the headers small
        request.headers["Accept"] = "*/*"

        LOG.info("Request %r %r ready for dispach (UUID: %s)",
                 request.method, request.uri, request.uuid)
        self._queue.push(request)
        start = time.time()
        while True:
            raw_response = self._queue.pop(request)
            if raw_response:
                response = _HTTPResponse.from_json(raw_response)
                break

            if time.time() - start > self._timeout:
                LOG.error("Request %s timeout.", request.uuid)
                start_response('504 Gateway Timeout', [])
                return [b'Something went wrong']

            time.sleep(self._delay)

        LOG.info("Response received for %r %r (UUID: %s",
                 request.method, request.uri, request.uuid)
        
        response_body = response.body.encode()
        response.headers["Content-Encoding"] = 'plain'
        response.headers["Content-Length"] = str(len(response_body))
        start_response(response.status, [(key, response.headers[key])
                                         for key in response.headers])
        return iter([response_body])

    def load_config(self):
        """The initial setup of the standalone application."""
        for key, value in iteritems(self._options):
            if value is not None and key in self.cfg.settings:
                self.cfg.set(key, value)

    def load(self):
        """Return the requests handler."""
        return self._dispatch


class ProxyWorker(demo_proxy_worker.ConcurrentWorker):
    """DemoProxy web worker."""

    def __init__(self, tasks_queue, delay, workers_count):
        super(ProxyWorker, self).__init__(delay, workers_count)
        self.queue = queue.Queue()
        self.stop = threading.Event()
        self._task_queue = tasks_queue

    def _task_generator(self):
        """Override this with your custom task generator."""
        while not self._stop_event.is_set():
            if self.queue.qsize() < self._workers_count:
                item = self._task_queue.get_request()
                if item:
                    yield item
            time.sleep(self._delay)

    def _get_task(self):
        """Retrieves a task from the shared queue."""
        while not self._stop_event.is_set():
            try:
                return self.queue.get_nowait()
            except queue.Empty:
                time.sleep(self._delay)

    def _put_task(self, task):
        """Add a new task into the internal queue."""
        request = _HTTPRequest.from_json(task)
        self.queue.put(request)

    def _work(self):
        request = self._get_task()
        if not request:
            print("Invalid request received.")
            return

        LOG.info("Request recived %r %r (UUID: %s)",
                 request.method, request.uri, request.uuid)
        response = requests.request(request.method, "https://example.com")
        status_code = "%d %s" % (response.status_code,
                                 http_client.responses[response.status_code])

        http_response = _HTTPResponse(
            method=request.method,
            status=status_code,
            headers=_HTTPHeaders.from_response(response),
            uri=request.uri,
            path=request.path,
            query=request.query,
            uuid=request.uuid,
            body=response.content.decode()
        )
        self._task_queue.set_response(request, http_response)

    def _start_worker(self):
        """Creates a new thread."""
        worker = threading.Thread(target=self._work)
        worker.setDaemon(True)
        worker.start()
        return worker
