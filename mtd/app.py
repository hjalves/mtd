import argparse
import asyncio
import importlib
import json
import logging
import logging.config
import os
import shutil
import time
from asyncio import gather
from asyncio import ensure_future
from pathlib import Path

import toml

from mtd.metric import MetricType
from mtd.pubsub import MetricPubSub
from mtd.wamp import create_component
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
        self.pubsub = MetricPubSub()
        self.config = self.load_config(self.config_file)
        self.webapp = create_webapp(self.config['web'], self.pubsub)
        self.wamp = create_component(self.config['wamp'], self.pubsub)

    def run(self):
        config = self.config
        logging.config.dictConfig(config['logging'])
        logging.captureWarnings(True)
        logger.info('Logging configured!')

        self.load_store_state()
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
            value = self.store.get(key, 0) + value
        else:
            value = value
        self.store[key] = value
        self.pubsub.publish(key, value)
        logger.debug('[%s] %s: %r', metric_type, key, value)

    async def main_loop(self):
        runner = await start_webapp(self.webapp, self.config['web'])
        running = True

        self.start_wamp(self.wamp)
        for plugin in self.plugins.values():
            self.start_plugin(plugin)

        logger.info("Updating with interval: %s", self.update_interval)
        while running:
            await self.update_plugins()
            self.save_store_state()
            await asyncio.sleep(self.update_interval)

        await runner.cleanup()

    def start_wamp(self, component):
        def component_done(fut):
            logger.warning("Component %r exited [%r]", component, fut.result())
        ensure_future(component.start()).add_done_callback(component_done)

    def start_plugin(self, plugin):
        def loop_done(fut):
            logger.warning("Plugin %r exited [%r]", plugin.name,
                        fut.result())
        ensure_future(plugin.loop()).add_done_callback(loop_done)

    def update_plugin(self, plugin):
        def update_done(fut):
            logger.debug("Plugin %r updated [%r]", plugin.name, fut.result())
        ensure_future(plugin.update()).add_done_callback(update_done)

    async def update_plugins(self):
        start = time.time()
        coros = [plugin.update() for plugin in self.plugins.values()]
        result = await gather(*coros, return_exceptions=True)
        failed = len([x for x in result if isinstance(x, Exception)])
        success = len(result) - failed
        logger.info("Updated plugins %s, failed %s [%.2f msec]: %s",
                     success, failed, (time.time() - start) * 1000, result)

    def load_store_state(self):
        file_path = self.config['store_location']
        try:
            with open(file_path) as f:
                self.store = json.load(f)
        except FileNotFoundError as ex:
            logger.warning(ex)

    def save_store_state(self):
        # TODO: this should not be blocking
        start = time.time()
        file_path = self.config['store_location']
        tempname = file_path + '.tmp'
        with open(tempname, 'w') as tempfile:
            json.dump(self.store, tempfile, indent=2)
        shutil.move(tempname, file_path)
        logger.info("Saved store in %s [%.2f msec]", file_path,
                    (time.time() - start) * 1000)

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
