"""Command line group for Demo-Proxy standalone application."""

import os
import signal
from tempfile import gettempdir
import multiprocessing

from demo_proxy import cli
from demo_proxy.common import exception
from demo_proxy.common import queue as demo_proxy_queue
from demo_proxy import wsd

PID_FILE = os.path.join(gettempdir(), "demo-proxy-server.pid")


class _Start(cli.Command):
    """Start the Demo-Proxy standalone application."""

    def setup(self):
        """Extend the parser configuration in order to expose this command."""
        cpu_count = multiprocessing.cpu_count() * 2 + 1

        parser = self._parser.add_parser(
            "start",
            help="Start the Demo-Proxy standalone application.")
        parser.add_argument(
            "--host", type=str, default="0.0.0.0",
            help="The IP address or the host name of the server. "
                 "Default: 0.0.0.0"
        )
        parser.add_argument(
            "--port", type=int, default=8080,
            help="The port that should be used by the current web service. "
                 "Default: 8080"
        )
        parser.add_argument(
            "--workers", type=int, default=cpu_count,
            help="The number of thread workers used in order to serve "
                 "clients. Default: %s" % cpu_count
        )
        parser.add_argument(
            "--redis-host", type=str, default="redis",
            help="The IP address or the host name of the Redis Server. "
                 "Default: redis"
        )
        parser.add_argument(
            "--redis-port", type=int, default=6379,
            help="The port that should be used for connecting to the"
                 "Redis Database. Default: 6379"
        )
        parser.add_argument(
            "--redis-database", type=int, default=0,
            help="The Redis database that should be used. Default: 0"
        )
        parser.set_defaults(work=self.run)

    def _work(self):
        """Start the Demo-Proxy standalone application."""
        pid = os.getpid()

        with open(PID_FILE, "w") as file_handle:
            file_handle.write(str(pid))

        queue = demo_proxy_queue.RedisQueue(self.args.redis_host,
                                            self.args.redis_port,
                                            self.args.redis_database)
        web_server = wsd.DemoProxy(
            tasks_queue=queue,
            bind="%s:%s" % (self.args.host, self.args.port),
            workers=self.args.workers)
        web_server.run()


class _Stop(cli.Command):
    """Stop the Demo-Proxy standalone application."""

    def setup(self):
        """Extend the parser configuration in order to expose this command."""
        parser = self._parser.add_parser(
            "stop", help="Stop the Demo-Proxy standalone application.")
        parser.set_defaults(work=self.run)

    def _work(self):
        """Stop the Demo-Proxy standalone application."""
        pid = None
        try:
            with open(PID_FILE, "r") as file_handle:
                pid = int(file_handle.read().strip())
        except (ValueError, OSError):
            raise exception.NotFound("Failed to get server PID.")

        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return False

        return True


class Server(cli.Group):
    """Group for all the available server actions."""

    commands = [(_Start, "actions"), (_Stop, "actions")]

    def setup(self):
        """Extend the parser configuration in order to expose this command."""
        parser = self._parser.add_parser(
            "server",
            help="Operations related to the Demo-Proxy "
                 "standalone application (start/stop).")

        actions = parser.add_subparsers()
        self._register_parser("actions", actions)
