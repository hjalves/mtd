import logging
from asyncio import ensure_future, gather

from collections import defaultdict

logger = logging.getLogger(__name__)


class MetricPubSub:

    def __init__(self):
        self.subscribers = defaultdict(set)

    def subscribe(self, prefix, subscriber):
        self.subscribers[prefix].add(subscriber)
        logger.info("Subscribed %s to prefix: %s", subscriber, prefix)

    def unsubscribe(self, subscriber):
        for subscriber_set in self.subscribers.values():
            subscriber_set.discard(subscriber)
        # TODO: Clean empty sets
        logger.info("Unsubscribed %s", subscriber)

    def publish(self, key, value):
        all_subscribers = set()
        for prefix, subscribers in self.subscribers.items():
            if key.startswith(prefix):
                all_subscribers.update(subscribers)
        if not all_subscribers:
            return
        task = ensure_future(self._async_publish(all_subscribers, key, value))
        task.add_done_callback(self._publish_callback)

    def _publish_callback(self, future):
        result = future.result()
        failed = len([x for x in result if isinstance(x, Exception)])
        success = len(result) - failed
        logger.debug("Published for %s, failed %s: %s", success, failed,
                     result)

    async def _async_publish(self, subscribers, key, value):
        coros = [sub.send_metric(key, value) for sub in subscribers]
        return await gather(*coros, return_exceptions=True)
