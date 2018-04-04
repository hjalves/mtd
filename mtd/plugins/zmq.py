
import json
import zmq.asyncio

from mtd.plugin import BasePlugin


class ZmqPlugin(BasePlugin):

    def stop(self):
        self.running = False

    async def loop(self):
        self.running = True
        host = self.config.get('host', '127.0.0.1')
        port = self.config.get('port', 5678)
        prefix = self.config.get('prefix', 'G')
        zmq_url = f'tcp://{host}:{port}'

        context = zmq.asyncio.Context()
        subscriber = context.socket(zmq.SUB)
        subscriber.setsockopt_string(zmq.SUBSCRIBE, prefix)

        self.logger.info("Connecting to %s", zmq_url)
        subscriber.connect(zmq_url)

        while self.running:
            _, plugin, data_raw = await subscriber.recv_multipart()
            data = json.loads(data_raw)
            plugin = plugin.decode()
            for key, value in data.items():
                sanitized_key = key.replace(' ', '_').replace('/', '_').lower()
                self.push(plugin + '.' + sanitized_key, value)
        subscriber.close()
        context.term()


Plugin = ZmqPlugin
