from .BaseLoader import BaseLoader, vk_api_call, timestamp_to_name
import progressbar

class WallLoader(BaseLoader):
    def __init__(self, session, path, wall_id="", count=50):
        super().__init__(session, path)
        self.bar_name = wall_id
        self.use_owner_id = False
    
        if wall_id.startswith('id'):
            wall_id = int(wall_id[2:])
            self.use_owner_id = True
        elif wall_id.startswith('club'):
            wall_id = -int(wall_id[4:])
            self.use_owner_id = True

        self.wall_id = wall_id
        self.count = count
        self.offset = 0

    async def _request_items(self):
        method_name = "wall.get"
        params = {
            "offset": self.offset,
            "count": self.count,
            "owner_id" if self.use_owner_id else "domain": self.wall_id
        }
        return await vk_api_call(self.session, "GET", method_name, **params)

    def _update_on_response(self, response):
        self.offset += self.count

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
            f"[{self.bar_name}] ",
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
