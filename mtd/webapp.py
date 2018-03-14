import asyncio
import logging
from pathlib import Path

from aiohttp import web

from mtd.utils import format_exception
from mtd.websocket import websocket_handler

logger = logging.getLogger(__name__)



def create_webapp(config, pubsub):
    webapp = web.Application(
        middlewares=[error_middleware],
        debug=config['debug_mode'],
        logger=logger
    )
    webapp['pubsub'] = pubsub
    webapp.router.add_get('/ws/', websocket_handler)
    return webapp


async def start_webapp(webapp, config):
    logger.warning("CONFIG: %s", config)
    runner = web.AppRunner(webapp)
    await runner.setup()
    if 'http_host' in config or 'http_port' in config:
        tcp_site = web.TCPSite(runner, config.get('http_host'),
                               config.get('http_port'))
        logger.info("Will start http on: %s", tcp_site.name)
        await tcp_site.start()
    if 'unix_socket' in config:
        unix_socket = Path(config['unix_socket']).absolute()
        unix_site = web.UnixSite(runner, unix_socket)
        logger.info("Will start unix on: %s", unix_site.name)
        await unix_site.start()
    return runner


async def cleanup_webapp(runner):
    await runner.cleanup()
    logger.info("Cleanup")


def json_error(error, status):
    message = {'error': error, 'status': status}
    return web.json_response(message, status=status)



@web.middleware
async def error_middleware(request, handler):
    try:
        response = await handler(request)
        if response is not None and response.status >= 400:
            return json_error(response.reason, response.status)
        return response
    except web.HTTPException as ex:
        if ex.status >= 400:
            return json_error(ex.reason, ex.status)
        raise
    except asyncio.CancelledError:
        raise
    except Exception as e:
        request.app.logger.exception(
            "Exception while handling request %s %s:", request.method,
            request.rel_url)
        return json_error(format_exception(e), 500)
