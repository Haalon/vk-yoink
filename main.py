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

        for domain in kwargs.get('wall', []):
            child_path = path_obj / 'walls' / domain
            child_path.mkdir(parents=True, exist_ok=True)
            loader = WallLoader(session, str(child_path), domain, count=count)
            await loader.run()

        for peer_id in kwargs.get('chat', []):
            child_path = path_obj / 'chats' / peer_id
            child_path.mkdir(parents=True, exist_ok=True)
            loader = ChatLoader(session, str(child_path), peer_id, count=count)
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

    parser.add_argument('-c', '--count', type=int, help='Amount of images to request from vk per api call', default=50)

    ns = parser.parse_args()
    asyncio.run(main(**ns.__dict__))