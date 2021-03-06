import logging

from autobahn.asyncio.component import Component
from autobahn.wamp import RegisterOptions
from txaio.aio import _TxaioLogWrapper

logger = logging.getLogger(__name__)


class WAMPSubscriber:

    def __init__(self):
        self.session = None

    async def send_metric(self, key, value):
        if self.session:
            self.session.publish('mtd.' + key, value)


def create_component(config, pubsub, query_func):
    subscriber = WAMPSubscriber()
    comp = Component(
        transports=config['router'],
        realm=config['realm'],
    )
    comp.log = _TxaioLogWrapper(logger.getChild('component'))

    @comp.on_join
    async def joined(session, details):
        logger.info("Session ready! %s %s", session, details)
        subscriber.session = session
        pubsub.subscribe('', subscriber)

    @comp.on_leave
    async def left(session, details):
        pubsub.unsubscribe(subscriber)
        subscriber.session = None
        logger.info("Session left! %s %s", session, details)

    @comp.register('mtd.query')
    async def query(*metrics):
        return query_func(*metrics)

    return comp
