from .BaseLoader import BaseLoader, vk_api_call, timestamp_to_name
import progressbar

class WallLoader(BaseLoader):
    def __init__(self, session, path, domain=""):
        super().__init__(session, path)
        self.domain = domain
        self.step = 50
        self.offset = 0

    async def _request_items(self):
        method_name = "wall.get"
        return await vk_api_call(self.session, "GET", method_name, offset=self.offset, count=self.step, domain=self.domain)

    def _update_on_response(self, response):
        self.offset += self.step

    def _item_to_tasks(self, item):
        post = item
        tasks = []
        for ind, attach in enumerate(post.get('attachments', {})):
            if attach['type'] != 'photo':
                continue

            url = attach['photo']['sizes'][-1]['url']
            name = f"{timestamp_to_name(int(post['date']))}-{ind:02}.jpg"
            tasks.append(self.download_image(url, name))

        return tasks

    def _get_bar(self, response):
        widgets=[
            f"[{self.domain}] ",
            progressbar.Counter(format='| post %(value).1f of %(max_value)d | '),
            progressbar.Percentage(),  ' ',
            progressbar.Bar(),
        ]
        bar = progressbar.ProgressBar(widgets=widgets, max_value=response['count'])
        
        return bar

    def _update_bar(self, bar):
        bar.update(min(self.offset, bar.max_value))

    def _is_finish(self, response):
        return self.offset >= response['count']
