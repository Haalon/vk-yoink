import asyncio
import aiohttp
from loaders import ChatLoader, FaveLoader, WallLoader
from pathlib import Path

async def main(path, count, **kwargs):
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        if kwargs['fave']:
            child_path = path_obj / 'faves'
            child_path.mkdir(parents=True, exist_ok=True)
            loader = FaveLoader(session, str(child_path), count=count)
            await loader.run()

        for ind, wall_id in enumerate(kwargs.get('wall', [])):
            offsets = kwargs.get('offset', [])
            offset = int(offsets[ind]) if ind < len(offsets)  else 0

            child_path = path_obj / 'walls' / wall_id
            child_path.mkdir(parents=True, exist_ok=True)
            loader = WallLoader(session, str(child_path), wall_id, count=count, offset=offset)
            await loader.run()

        for ind, peer_id in enumerate(kwargs.get('chat', [])):
            starts = kwargs.get('start_from', [])
            start_from = starts[ind] if ind < len(starts) else ""

            child_path = path_obj / 'chats' / peer_id
            child_path.mkdir(parents=True, exist_ok=True)
            loader = ChatLoader(session, str(child_path), peer_id, count=count, start_from=start_from)
            await loader.run()


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

    parser.add_argument('--offset', nargs='+', help='Specify offsets for walls - from what post to start loading. \
        In case of many walls, offsets can be specified in order of appearances',
        default=[], metavar=("0",  "150"))

    parser.add_argument('--start-from', nargs='+', help='Specify starts for chats - from what message to start loading. \
        In case of many chats, starts can be specified in order of appearances',
        default=[], metavar=("1753228/1",  "1239741/2"))

    parser.add_argument('-c', '--count', type=int, help='Amount of images to request from vk per api call', default=50)

    ns = parser.parse_args()
    asyncio.run(main(**ns.__dict__))