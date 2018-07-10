"""Simple queue used for server-worker communication."""

import abc

import six

from demo_proxy.common import utils


@six.add_metaclass(abc.ABCMeta)
class _Queue(object):
    """Contract class for the remote queue."""

    @abc.abstractmethod
    def push(self, request):
        """Add a new request in the processing queue."""
        pass

    @abc.abstractmethod
    def pop(self, request):
        """Get the response for the received request (if available)."""
        pass


class RedisQueue(_Queue):

    """Simple Redis queue."""

    def __init__(self, host, port, database):
        self._conn = utils.RedisConnection(host, port, database)

    def push(self, request):
        """Add request to the processing queue."""
        conn = self._conn.rcon
        conn.lpush("request", request.to_json())

    def pop(self, request):
        """Get response if available."""
        conn = self._conn.rcon
        if conn.hexists("response", request.uuid):
            response = conn.hget("response", request.uuid)
            conn.hdel("response", request.uuid)
            return response

    def get_request(self):
        """Get the first item in queue to be processed."""
        conn = self._conn.rcon
        return conn.rpop("request")

    def set_response(self, request, response):
        """Add the response for the received request."""
        conn = self._conn.rcon
        conn.hset("response", request.uuid, response.to_json())
