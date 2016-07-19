from gevent import monkey
monkey.patch_all()

import os
import sys
import signal
import threading

import flask
import gevent

from flask_cors import CORS
from flask_socketio import SocketIO

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

from scrapy_eagle.dashboard import config
from scrapy_eagle.dashboard import memory
from scrapy_eagle.dashboard.green_threads import heartbeat, stats
from scrapy_eagle.dashboard.utils import process


app = flask.Flask(__name__)


def main():

    # Install the arguments and config file inside the config module
    _, _ = config.setup()


def shutdown():

    # Send a signal to all opened subprocess, closing them.
    for pid, _, _, _ in config.subprocess_pids:

        print('killing subprocess: {pid}'.format(pid=pid))

        os.kill(pid, signal.SIGHUP)

    print('\nshutting down {0}...'.format(threading.currentThread().getName()))

    sys.exit(0)


def start_periodics(socketio):

    redis_conn = memory.get_connection()
    public_ip = config.get_public_ip()
    hostname = config.get_hostname()

    for i in range(3):
        gevent.spawn(
            process.new_subprocess,
            base_dir='.',
            subprocess_pids=config.subprocess_pids,
            queue_info_global=config.queue_info_global,
            buffers=config.buffers
        )

    gevent.spawn(heartbeat.heartbeat_servers, redis_conn, public_ip, hostname)
    gevent.spawn(stats.send_resources_info, socketio, config.subprocess_pids, public_ip)


def entry_point():

    # Graceful shutdown when kill are received
    signal.signal(signal.SIGTERM, lambda sig, frame: shutdown())

    # Graceful shutdown when terminal session are closed
    signal.signal(signal.SIGHUP, lambda sig, frame: shutdown())

    main()

    try:

        app.config['SECRET_KEY'] = 'ha74%ahtus342'
        app.config['DEBUG'] = True

        from scrapy_eagle.dashboard.views import servers

        app.register_blueprint(servers.servers, url_prefix='/servers')

        CORS(app)

        socketio = SocketIO(app, async_mode='gevent')

        start_periodics(socketio)

        # use_reloader: avoid Flask execute twice
        socketio.run(app, host='0.0.0.0', port=5001, use_reloader=False)

    except (KeyboardInterrupt, SystemExit):

        shutdown()


if __name__ == "__main__":

    entry_point()
