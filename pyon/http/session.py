from .response import HTTPResponse

class HTTPClient:
    def __init__(
            self,
            base_url: str = "",
            headers: dict[str, str] | None = None,
            params: dict[str, str] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.params = params or {}

    def _prepare_kwargs(self, url: str, kwargs: dict) -> tuple[str, dict]:
        if self.base_url and url.startswith("/"):
            final_url = f"{self.base_url}{url}"
        elif self.base_url and not url.startswith("http"):
            final_url = f"{self.base_url}/{url}"
        else:
            final_url = url

        req_headers = kwargs.pop("headers", {})
        final_headers = {**self.headers, **req_headers}
        if final_headers:
            kwargs["headers"] = final_headers

        req_params = kwargs.pop("params", {})
        final_params = {**self.params, **req_params}
        if final_params:
            kwargs["params"] = final_params

        return final_url, kwargs

    async def request(self, method: str, url: str, **kwargs) -> HTTPResponse:
        from .client import request as core_request

        final_url, final_kwargs = self._prepare_kwargs(url, kwargs)

        return await core_request(method, final_url, **final_kwargs)

    async def get(self, url: str, **kwargs) -> HTTPResponse: return await self.request("GET", url, **kwargs)
    async def post(self, url: str, **kwargs) -> HTTPResponse: return await self.request("POST", url, **kwargs)
    async def put(self, url: str, **kwargs) -> HTTPResponse: return await self.request("PUT", url, **kwargs)
    async def patch(self, url: str, **kwargs) -> HTTPResponse: return await self.request("PATCH", url, **kwargs)
    async def delete(self, url: str, **kwargs) -> HTTPResponse: return await self.request("DELETE", url, **kwargs)
    