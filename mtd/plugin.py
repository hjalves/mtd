import logging

from mtd.metric import MetricType

logger = logging.getLogger(__name__)


class BasePlugin:

    def __init__(self, app, name, config):
        self.app = app
        self.name = name
        self.config = config
        self.logger = logger.getChild(name)

    def push(self, key, value, metric_type=MetricType.AUTO):
        return self.app.push(self.name, metric_type, key, value)

    def stop(self):
        self.logger.warning('no stop()')

    async def loop(self):
        pass

    async def update(self):
        pass

    def __repr__(self):
        return f'<{self.__class__.__name__} ' \
               f'name={self.name!r} ' \
               f'config={self.config!r}>'
