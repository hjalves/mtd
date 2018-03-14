import json
import logging

from aiohttp import WSMsgType
from aiohttp.web_ws import WebSocketResponse

from mtd.utils import format_exception, json_dumps

logger = logging.getLogger(__name__)


async def websocket_handler(request):
    ws = WebsocketHandler(request)
    response = await ws.loop()
    return response


class WebsocketHandler:

    def __init__(self, request):
        self.request = request
        self.remote = request.remote
        self.peername = request.transport.get_extra_info('peername')
        self.pubsub = request.app['pubsub']
        self.response = WebSocketResponse()

    def __repr__(self):
        return f"<WebsocketSubscriber {self.remote}: {self.peername}>"

    async def send_metric(self, key, value):
        message = json_dumps({key: value})
        await self.response.send_str(message)

    async def send_json(self, *a, **kw):
        data = dict(*a, **kw)
        message = json_dumps(data)
        await self.response.send_str(message)

    async def loop(self):
        await self.response.prepare(self.request)
        logger.debug("ws prepared")

        async for msg in self.response:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    self._parse_command(data)
                except Exception as e:
                    await self.send_json(error=format_exception(e))
                    logger.exception('Exception in message %r', msg)
            elif msg.type == WSMsgType.ERROR:
                logger.error('ws connection closed with exception %s',
                             self.response.exception())
                break
            else:
                logger.warning("ws message: %s", msg)

        self.pubsub.unsubscribe(self)
        logger.debug("Websocket closed: %r", self)
        return self.response

    def _parse_command(self, data):
        if 'subscribe' in data and isinstance(data['subscribe'], str):
            self.pubsub.subscribe(data['subscribe'], self)
        else:
            raise ValueError("invalid command")
