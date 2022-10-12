from .BaseLoader import BaseLoader, vk_api_call, timestamp_to_name
import progressbar


class ChatLoader(BaseLoader):
    def __init__(self, session, path, peer_id="", count=50, start_from=""):
        super().__init__(session, path)
        self.old_peer = peer_id

        # case of chat room
        if peer_id[0] == 'c':
            peer_id = int(peer_id[1:]) + 2000000000
        else:
            peer_id = int(peer_id)
        self.peer_id = peer_id
        self.count = count
        self.start_from = start_from

    async def _request_items(self):
        method_name = "messages.getHistoryAttachments"
        return await vk_api_call(self.session, "GET", method_name, 
            media_type='photo', start_from=self.start_from, count=self.count, peer_id=self.peer_id)

    def _update_on_response(self, response):
        self.start_from = response.get('next_from')

        if self.start_from:
            self.current = int(self.start_from.split('/')[0])

    def _item_to_tasks(self, item):
        tasks = []
        photo = item['attachment']['photo']
        url = photo['sizes'][-1]['url']
        id_ = photo['id']
        name = timestamp_to_name(photo['date']) + f"-{id_}.jpg"
        tasks.append(self.download_image(url, name))

        return tasks

    def _get_bar(self, response):
        widgets=[
            f"[@{self.old_peer}] ",
            "| ",  progressbar.Variable('start_from'), " ",
            progressbar.BouncingBar(),
        ]
        bar = progressbar.ProgressBar(widgets=widgets)
        
        return bar

    def _update_bar(self, bar):
        bar.update(0, force=True, start_from=self.start_from)

    def _is_finish(self, response):
        return not self.start_from