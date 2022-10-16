from abc import ABC, abstractmethod
from typing import Any, Awaitable
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
logger.add(sys.stderr, format="<level>{time} | {level: ^8} | {message}</level>", colorize=True, level="INFO")
logger.add("./err.log", format="<level>{time} | {level: ^8} | {message}</level>", colorize=False, level="ERROR")


load_dotenv()
TOKEN = os.getenv('TOKEN')
V = '5.131'
ENDPOINT = "https://api.vk.com/method/"

def timestamp_to_name(unix_ts: str) -> str:
    dt_object = datetime.fromtimestamp(unix_ts)
    return dt_object.strftime(r"%Y%m%d-%H%M%S")

async def fetch_content_stream(url: str, session: aiohttp.ClientSession, **kwargs) -> aiohttp.StreamReader:
    """GET request wrapper to fetch content stream.

    kwargs are passed to `session.request()`.
    """

    resp = await session.request(method="GET", url=url, **kwargs)
    resp.raise_for_status()
    stream = resp.content
    return stream

async def vk_api_call(session: aiohttp.ClientSession, method: str, method_name: str, **kwargs) -> Any:
    params= {'access_token': TOKEN, 'v':V, **kwargs}
    url = f"{ENDPOINT}{method_name}"
    resp = await session.request(method=method, url=url, params=params)
    resp.raise_for_status()
    logger.info("Got response [{}] for URL: {}", resp.status, url)
    json = await resp.json()
    return json


class BaseLoader(ABC):
    SHUTDOWN_FLAG = False

    def __init__(self, session: aiohttp.ClientSession, path: str):
        self.session = session
        self.path = path
        self.logger = logger

    @abstractmethod
    async def _request_items(self) -> Any:
        """
        Request items to download

        Usually posts or photoes

        """

    @abstractmethod
    def _update_on_response(self, response):
        """
        Update instance props, so the next call to _request_items
        will request next set of items
        """

    @abstractmethod
    def _get_bar(self, response) -> progressbar.ProgressBar:
        """Create progressbar based on an initial response from _request_items"""

    @abstractmethod
    def _update_bar(self, bar):
        """Update bar on each iteration"""

    @abstractmethod
    def _item_to_tasks(self, item: Any) -> [Awaitable]:
        """
        Map items, returned from _request_items, to coroutine tasks
        """

    @abstractmethod
    def _is_finish(self, response) -> bool:
        """Check if there is nothing left to download"""

    async def run(self):
        """Run the loading loop, until everything is downloaded or until an error"""
        # init loop
        bar = None
        while not BaseLoader.SHUTDOWN_FLAG:
            try:
                response = await self._request_items()
            except (
                aiohttp.ClientError,
                aiohttp.http_exceptions.HttpProcessingError,
                aiohttp.client_exceptions.ClientPayloadError,
            ) as err:
                logger.error(str(err))
                break

            # vk api may return error
            # for example if try to request posts from blocked group
            err = response.get('error')
            if err:
                logger.critical(err['error_msg'])
                break

            response = response['response']

            if not bar:
                bar = self._get_bar(response)
                bar.start()
                self._update_bar(bar)

            self._update_on_response(response)

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

    async def download_image(self, url: str, name: str):
        """
        Download image from given url and save it to the loader's path with a given name
        """
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
            logger.error(str(err))
            return

        async with aiofiles.open(fullpath, mode='wb') as f:
            async for block in content_stream.iter_any():
                await f.write(block)

        logger.success("Image [{}] downloaded", name)

# register SIGINT listener to shutdown loop gracefully
def signal_handler(signal, frame):
    BaseLoader.SHUTDOWN_FLAG = True
    logger.warning("Shutting down")

signal.signal(signal.SIGINT, signal_handler)