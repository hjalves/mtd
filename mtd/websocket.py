import logging

from aiohttp import WSMsgType
from aiohttp.web_ws import WebSocketResponse

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

    async def send_message(self, message):
        await self.response.send_str(message)

    async def loop(self):
        await self.response.prepare(self.request)
        logger.debug("ws prepared")

        async for msg in self.response:
            if msg.type == WSMsgType.TEXT:
                text = msg.data

                logger.info("ws received text: %r", text)
            elif msg.type == WSMsgType.ERROR:
                logger.error('ws connection closed with exception %s',
                             self.response.exception())
                break
            else:
                logger.warning("ws message: %s", msg)

        logger.debug("Websocket closed: %r", self)
        return self.response
