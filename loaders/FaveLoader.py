from .BaseLoader import vk_api_call
from .WallLoader import WallLoader

class FaveLoader(WallLoader):
    def __init__(self, session, path, count=50):
        super().__init__(session, path, count=count)
        self.domain = "#fave"

    async def _request_items(self):
        method_name = "fave.getPosts"
        return await vk_api_call(self.session, "GET", method_name, offset=self.offset, count=self.count, domain=self.domain)