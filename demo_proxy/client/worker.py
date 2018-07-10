"""Command line group for DemoProxy web worker."""

import os
import signal
from tempfile import gettempdir
import multiprocessing

from demo_proxy import cli
from demo_proxy.common import exception
from demo_proxy.common import queue as demo_proxy_queue
from demo_proxy import wsd

PID_FILE = os.path.join(gettempdir(), "demo-proxy-worker.pid")


class _Start(cli.Command):
    """Start the demo_proxy web worker."""

    def setup(self):
        """Extend the parser configuration in order to expose this command."""
        cpu_count = multiprocessing.cpu_count() * 2 + 1

        parser = self._parser.add_parser(
            "start",
            help="Start the demo_proxy web worker.")
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
        """Start the demo_proxy web worker."""
        pid = os.getpid()
        with open(PID_FILE, "w") as file_handle:
            file_handle.write(str(pid))

        queue = demo_proxy_queue.RedisQueue(self.args.redis_host,
                                            self.args.redis_port,
                                            self.args.redis_database)
        web_worker = wsd.ProxyWorker(
            tasks_queue=queue,
            workers_count=self.args.workers,
            delay=0.1)
        web_worker.run()


class _Stop(cli.Command):
    """Stop the demo_proxy web worker."""

    def setup(self):
        """Extend the parser configuration in order to expose this command."""
        parser = self._parser.add_parser(
            "stop", help="Stop the demo_proxy web worker.")
        parser.set_defaults(work=self.run)

    def _work(self):
        """Stop the demo_proxy web worker."""
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


class Worker(cli.Group):
    """Group for all the available server actions."""

    commands = [(_Start, "actions"), (_Stop, "actions")]

    def setup(self):
        """Extend the parser configuration in order to expose this command."""
        parser = self._parser.add_parser(
            "worker",
            help="Operations related to the demo_proxy "
                 "web worker (start/stop).")

        actions = parser.add_subparsers()
        self._register_parser("actions", actions)
