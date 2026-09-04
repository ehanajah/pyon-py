from pyon.browser import FetchResponse

from .exceptions import HTTPStatusError

class HTTPResponse:
    def __init__(self, raw_response: FetchResponse) -> None:
        self._res = raw_response

    @property
    def status_code(self) -> int:
        return self._res.status
    
    @property
    def ok(self) -> bool:
        return self._res.ok

    @property
    def url(self) -> str:
        return self._res.url

    @property
    def headers(self) -> dict[str, str]:
        return dict(self._res.headers.items())

    async def json(self) -> dict:
        return await self._res.json()

    async def text(self) -> str:
        return await self._res.string()

    def raise_for_status(self) -> None:
        if not self.ok:
            raise HTTPStatusError(
                f"HTTP error {self.status_code} for url '{self.url}'",
                self.status_code,
                self.url
            )