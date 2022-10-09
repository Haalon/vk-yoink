import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

import aiofiles
import aiohttp
from dotenv import load_dotenv
import progressbar
# flush to work with logging
progressbar.streams.wrap_stderr()

GREEN = "\x1b[32;20m"
RESET = "\x1b[0m"

logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S",
)

load_dotenv()
TOKEN = os.getenv('TOKEN')
V = '5.131'
ENDPOINT = "https://api.vk.com/method/"

async def vk_api_call(session, method, method_name, **kwargs):
    params= {'access_token': TOKEN, 'v':V, **kwargs}
    url = f"{ENDPOINT}{method_name}"
    resp = await session.request(method=method, url=url, params=params)
    resp.raise_for_status()
    logging.info("Got response [%s] for URL: %s", resp.status, url)
    json = await resp.json()
    return json['response']


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

async def download_image(session, url, name, path, **kwargs):
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
        aiohttp.client_exceptions.ClientPayloadError,
    ) as err:
        logging.error(
            "aiohttp exception for %s [%s]: %s",
            url,
            getattr(err, "status", None),
            getattr(err, "message", None),
        )
        return

    async with aiofiles.open(fullpath, mode='wb') as f:
        async for block in content_stream.iter_any():
            await f.write(block)

async def download_post(session, post, path, **kwargs):
    tasks = []
    for ind, attach in enumerate(post.get('attachments', {})):
        if attach['type'] != 'photo':
            continue

        url = attach['photo']['sizes'][-1]['url']
        name = f"{timestamp_to_name(int(post['date']))}-{ind:02}.jpg"
        tasks.append(download_image(session, url, name, path, **kwargs))

    await asyncio.gather(*tasks)

def download_fave(session, path, **kwargs):
    return _download_posts(session, path, 'fave', **kwargs)

def download_wall(session, path, domain, **kwargs):
    return _download_posts(session, path, 'wall', domain=domain, **kwargs)

async def download_chat(session, path, peer_id, **kwargs):
    method_name = "messages.getHistoryAttachments"
    bar = None
    old_peer = peer_id
    # case of chat room
    if peer_id[0] == 'c':
        peer_id = int(peer_id[1:]) + 2000000000
    else:
        peer_id = int(peer_id)

    start_from=""
    total = 0
    while True:
        res = await vk_api_call(session, "GET", method_name, peer_id=peer_id,
            start_from=start_from, media_type='photo', count=50, **kwargs)

        start_from = res['next_from']
        current = int(start_from.split('/')[0])

        photo_objs = (item['attachment']['photo'] for item in res['items'])

        if not start_from or not photo_objs:
            bar.finish()
            break

        if not bar:
            total = int(start_from.split('/')[0])
            widgets=[
                f"[@{old_peer}] ",
                progressbar.Counter(format='| msg %(value)d of %(max_value)d | '),
                progressbar.Percentage(), ' ',
                progressbar.Bar(),
            ]
            bar = progressbar.ProgressBar(widgets=widgets,max_value=total).start()

        tasks = []
        for photo in photo_objs:
            url = photo['sizes'][-1]['url']
            id_ = photo['id']
            name = timestamp_to_name(photo['date']) + f"-{id_}.jpg"
            tasks.append(download_image(session, url, name, path))

        await asyncio.gather(*tasks)
        bar.update(total - current)


async def _download_posts(session, path, type_='fave', step = 50, **kwargs):
    offset = 0
    method_name = "fave.getPosts" if type_ == 'fave' else "wall.get"
    bar = None
    while True:
        res = await vk_api_call(session, "GET", method_name, offset=offset, count=step, **kwargs)

        if not bar:
            widgets=[
                f"[{'#fave' if type_ == 'fave' else kwargs.get('domain')}] ",
                progressbar.Counter(format='| post %(value)d of %(max_value)d | '),
                progressbar.Percentage(),  ' ',
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
            child_path = path_obj / 'faves'
            child_path.mkdir(parents=True, exist_ok=True)
            await download_fave(session, str(child_path))

        for domain in kwargs.get('wall', []):
            child_path = path_obj / 'walls' / domain
            child_path.mkdir(parents=True, exist_ok=True)
            await download_wall(session, str(child_path), domain)

        for peer_id in kwargs.get('chat', []):
            child_path = path_obj / 'chats' / peer_id
            child_path.mkdir(parents=True, exist_ok=True)
            await download_chat(session, str(child_path), peer_id)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--path", default='./data', help="Path to save images to")
    parser.add_argument('--wall', nargs='+', help='Domain(s) of users/groups to download from',
        default=[], metavar=("user_id", "group_id"))

    parser.add_argument('--chat', nargs='+', help='Chat peer_id\'s to download from',
        default=[], metavar=("c42",  "-42069"))

    parser.add_argument('--fave', help='If set, download images from liked posts (bookmarks)',
        default=False, action='store_true')

    ns = parser.parse_args()
    asyncio.run(main(**ns.__dict__))
