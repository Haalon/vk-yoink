import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import aiofiles
import aiohttp
from dotenv import load_dotenv
import progressbar
# flush to work with logging
progressbar.streams.wrap_stderr()

green = "\x1b[32;20m"
reset = "\x1b[0m"

logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S",
)

load_dotenv()
TOKEN = os.getenv('TOKEN')
v = '5.131'
endpoint = "https://api.vk.com/method/"

async def vk_api_call(session, method, method_name, **kwargs):
    params= {'access_token': TOKEN, 'v':v, **kwargs}
    url = f"{endpoint}{method_name}"
    resp = await session.request(method=method, url=url, params=params)
    resp.raise_for_status()
    logging.info("Got response [%s] for URL: %s", resp.status, url)
    json = await resp.json()
    return json['response']


def timestamp_to_name(ts):
    dt_object = datetime.fromtimestamp(ts)
    return dt_object.strftime(r"%Y%m%d-%H%M%S")

async def fetch_content_stream(url: str, session, **kwargs) -> str:
    """GET request wrapper to fetch content stream.

    kwargs are passed to `session.request()`.
    """

    resp = await session.request(method="GET", url=url, **kwargs)
    resp.raise_for_status()
    stream = resp.content
    return stream

async def downloadImage(session, url, name, path, **kwargs):
    fullpath = os.path.join(path, name)
    if os.path.exists(fullpath):
        logging.info("Image [%s] already exists", name)
        return

    logging.info("Downloading image [%s] with URL: %s", name, url)
    try:
        content_stream = await fetch_content_stream(url=url, session=session)
    except (
        aiohttp.ClientError,
        aiohttp.http_exceptions.HttpProcessingError,
    ) as e:
        logloggerging.error(
            "aiohttp exception for %s [%s]: %s",
            url,
            getattr(e, "status", None),
            getattr(e, "message", None),
        )
        return
    
    async with aiofiles.open(fullpath, mode='wb') as f:
        async for line in content_stream.iter_chunked(1024):
            await f.write(line)


async def download_post(session, post, path, **kwargs):
    tasks = []
    for ind, attach in enumerate(post.get('attachments', {})):
        if attach['type'] != 'photo':
            continue

        url = attach['photo']['sizes'][-1]['url']
        name = f"{timestamp_to_name(int(post['date']))}-{ind:02}.jpg"
        tasks.append(downloadImage(session, url, name, path, **kwargs))
    
    await asyncio.gather(*tasks)

def download_fave(session, path, **kwargs):
    return _download_posts(session, path, 'fave', **kwargs)

def download_wall(session, path, domain, **kwargs):
    return _download_posts(session, path, 'wall', domain=domain, **kwargs)

async def _download_posts(session, path, type='fave', step = 50, **kwargs):
    offset = 0
    method_name = "fave.getPosts" if type == 'fave' else "wall.get"
    bar = None
    while True:
        logging.info(f"{green}Loading {step} posts with offset {offset}{reset}")
        res = await vk_api_call(session, "GET", method_name, offset=offset, count=step, **kwargs)

        # progressbar shows percentage of all posts
        if not bar:
            widgets=[
                f"[{'#fave' if type == 'fave' else kwargs.get('domain')}] ",
                progressbar.Counter(format='%(value)02d/%(max_value)d'),
                progressbar.Bar(),
            ]
            bar = progressbar.ProgressBar(widgets=widgets, max_value=res['count']).start()

        offset += step

        tasks = [download_post(session, post, path, **kwargs) for post in res['items']]
        await asyncio.gather(*tasks)

        bar.update(min(offset, res['count']))

        if offset >= res['count']:
            bar.finish()
            break

async def main(path, **kwargs):
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        if kwargs['fave']:
            child_path = path_obj / '#fave'
            child_path.mkdir(parents=True, exist_ok=True)
            await download_fave(session, str(child_path), **kwargs)
        
        for domain in kwargs.get('wall', []):
            child_path = path_obj / domain
            child_path.mkdir(parents=True, exist_ok=True)
            await download_wall(session, str(child_path), domain, **kwargs)
        
                
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--path", default='./data', help="Path to save images to")
    parser.add_argument('--wall', nargs='+', help='Domain(s) of users/groups to download from', 
        default=[], metavar=["userId1", "groupId2"])

    parser.add_argument('--fave', help='If set, download images from liked posts (bookmarks)', 
        default=False, action='store_true')

    ns = parser.parse_args()
    asyncio.run(main(**ns.__dict__))