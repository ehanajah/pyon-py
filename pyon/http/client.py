import json
import urllib.parse
from pyon.browser import fetch
from .response import HTTPResponse

async def request(method: str, url: str, **kwargs) -> HTTPResponse:
    if "params" in kwargs:
        params_dict = kwargs.pop("params")
        query_string = urllib.parse.urlencode(params_dict, doseq=True)
        if "?" in url:
            url = f"{url}&{query_string}"
        else:
            url = f"{url}?{query_string}"

    if "json" in kwargs:
        payload = kwargs.pop("json")
        kwargs["body"] = json.dumps(payload)
        headers = kwargs.get("headers", {})
        headers["Content-Type"] = "application/json"
        kwargs["headers"] = headers
    
    raw_response = await fetch(url, method=method, **kwargs)
    return HTTPResponse(raw_response)

async def get(url: str, **kwargs) -> HTTPResponse:
    return await request("GET", url, **kwargs)

async def post(url: str, **kwargs) -> HTTPResponse:
    return await request("POST", url, **kwargs)

async def put(url: str, **kwargs) -> HTTPResponse:
    return await request("PUT", url, **kwargs)

async def patch(url: str, **kwargs) -> HTTPResponse:
    return await request("PATCH", url, **kwargs)

async def delete(url: str, **kwargs) -> HTTPResponse:
    return await request("DELETE", url, **kwargs)
