from abc import ABC, abstractmethod
import asyncio
import os
import signal
import sys
from datetime import datetime

import aiofiles
import aiohttp
import progressbar
from dotenv import load_dotenv

from loguru import logger
# flush to work with logger
progressbar.streams.wrap_stderr()

logger.remove() 
logger.add(sys.stderr, format="<level>{time} | {level} | {message}</level>", colorize=True, level="INFO")


load_dotenv()
TOKEN = os.getenv('TOKEN')
V = '5.131'
ENDPOINT = "https://api.vk.com/method/"

def timestamp_to_name(unix_ts):
    dt_object = datetime.fromtimestamp(unix_ts)
    return dt_object.strftime(r"%Y%m%d-%H%M%S")

async def fetch_content_stream(url: str, session, **kwargs) -> str:
    """GET request wrapper to fetch content stream.

    kwargs are passed to `session.request()`.
    """

    resp = await session.request(method="GET", url=url, **kwargs)
    resp.raise_for_status()
    stream = resp.content
    return stream

async def vk_api_call(session, method, method_name, **kwargs):
    params= {'access_token': TOKEN, 'v':V, **kwargs}
    url = f"{ENDPOINT}{method_name}"
    resp = await session.request(method=method, url=url, params=params)
    resp.raise_for_status()
    logger.info("Got response [{}] for URL: {}", resp.status, url)
    json = await resp.json()
    return json


class BaseLoader(ABC):
    SHUTDOWN_FLAG = False

    def __init__(self, session, path):
        self.session = session
        self.path = path

    @abstractmethod
    async def _request_items(self):
        pass

    @abstractmethod
    def _update_on_response(self, response):
        pass

    @abstractmethod
    def _get_bar(self, response):
        pass

    @abstractmethod
    def _update_bar(self, bar):
        pass

    @abstractmethod
    def _item_to_tasks(self, item):
        pass

    @abstractmethod
    def _is_finish(self, response):
        pass

    async def run(self):
        # init loop
        bar = None
        while not BaseLoader.SHUTDOWN_FLAG:
            response = await self._request_items()
            err = response.get('error')
            if err:
                logger.critical(err['error_msg'])
                break
            
            response = response['response']
            self._update_on_response(response)


            if not bar:
                bar = self._get_bar(response)
                bar.start()

            tasks = [task for item in response['items'] for task in self._item_to_tasks(item)]

            curr_value = bar.value
            counter = 0
            # one item may have created many tasks, or none
            ratio = len(response['items']) / len(tasks)
            for task in asyncio.as_completed(tasks):
                await task
                bar.update(curr_value + counter, force=True)
                counter+= ratio

            self._update_bar(bar)

            if self._is_finish(response):
                bar.finish()
                break

    async def download_image(self, url, name):
        path = self.path
        session = self.session
        fullpath = os.path.join(path, name)
        if os.path.exists(fullpath):
            logger.info("Image [{}] already exists", name)
            return

        logger.info("Downloading image [{}] with URL: {}", name, url)
        try:
            content_stream = await fetch_content_stream(url=url, session=session)
        except (
            aiohttp.ClientError,
            aiohttp.http_exceptions.HttpProcessingError,
            aiohttp.client_exceptions.ClientPayloadError,
        ) as err:
            logger.error(
                "aiohttp exception for {} [{}]: {}",
                url,
                getattr(err, "status", None),
                getattr(err, "message", None),
            )
            return

        async with aiofiles.open(fullpath, mode='wb') as f:
            async for block in content_stream.iter_any():
                await f.write(block)

# register SIGINT listener to shutdown loop gracefully
def signal_handler(signal, frame):
    BaseLoader.SHUTDOWN_FLAG = True
    logger.warning("Shutting down")

signal.signal(signal.SIGINT, signal_handler)