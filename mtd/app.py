import argparse
import asyncio
import importlib
import logging
import logging.config
from asyncio import ensure_future
from pathlib import Path

from aiohttp import web
import toml

from mtd.metric import MetricType
from mtd.webapp import create_webapp, start_webapp

logger = logging.getLogger(__name__)
here_path = Path(__file__).parent


def main(args=None):
    parser = argparse.ArgumentParser(description='mtd: metrics daemon')
    parser.add_argument('-c', '--config', required=True,
                        type=argparse.FileType('r'),
                        help='Configuration file')
    args = parser.parse_args(args)
    return App(config_file=args.config).run()




class App:
    def __init__(self, config_file):
        self.config_file = config_file
        self.store = {}
        self.config = self.load_config(self.config_file)
        self.webapp = create_webapp(self.config['web'])

    def run(self):
        config = self.config
        logging.config.dictConfig(config['logging'])
        logging.captureWarnings(True)
        logger.info('Logging configured!')

        self.update_interval = config.get('update_interval', 30)

        plugins_conf = config.get('plugins', {})
        self.plugins = self.load_plugins(plugins_conf)
        logger.info("Loaded plugins: %s", self.plugins)

        loop = asyncio.get_event_loop()
        try:
            result = loop.run_until_complete(self.main_loop())
            print("returned:", result)
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        return result

    def push(self, plugin_name, metric_type, key, value):
        key = plugin_name + '.' + key
        if metric_type == MetricType.COUNTER:
            self.store[key] = self.store.get(key, 0) + value
        else:
            self.store[key] = value
        logger.debug('[%s] %s: %r', metric_type, key, self.store[key])

    async def main_loop(self):
        runner = await start_webapp(self.webapp, self.config['web'])
        running = True

        for plugin in self.plugins.values():
            self.start_plugin(plugin)

        logger.info("Updating with interval: %s", self.update_interval)
        while running:
            for plugin in self.plugins.values():
                self.update_plugin(plugin)
            await asyncio.sleep(self.update_interval)

        await runner.cleanup()

    def start_plugin(self, plugin):
        def loop_done(fut):
            logger.warning("Plugin %r exited [%r]", plugin.name,
                        fut.result())
        ensure_future(plugin.loop()).add_done_callback(loop_done)

    def update_plugin(self, plugin):
        def update_done(fut):
            logger.debug("Plugin %r updated [%r]", plugin.name, fut.result())
        ensure_future(plugin.update()).add_done_callback(update_done)

    def load_plugins(self, plugins_config):
        plugins = {}
        for name, conf in plugins_config.items():
            plugin_type = conf.pop('plugin', name)
            module = importlib.import_module('.plugins.' + plugin_type, 'mtd')
            plugin = module.Plugin(self, name, conf)
            plugins[name] = plugin
        return plugins

    @staticmethod
    def load_config(file):
        if isinstance(file, (str, Path)):
            file = open(file)
        with file:
            config = toml.load(file)
        return config
