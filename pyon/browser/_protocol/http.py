from collections.abc import Coroutine
from typing import Any, Protocol


class AbortController(Protocol):
    """
    Protocol for the AbortController class.
    """
    @property
    def signal(self) -> Any: ...
    def abort(self) -> None: ...

    
class FetchResponse(Protocol):
    """
    Protocol for the response object returned by pyfetch.
    """
    @property
    def ok(self) -> bool: ...

    @property
    def status(self) -> int: ...

    @property
    def status_text(self) -> str: ...

    @property
    def url(self) -> str: ...
    
    @property
    def headers(self) -> Any: ...

    async def json(self) -> Any: ...
    async def string(self) -> str: ...
    async def bytes(self) -> bytes: ...
    async def memoryview(self) -> memoryview: ...
    async def clone(self) -> "FetchResponse": ...


class Fetch(Protocol):
    """
    Protocol for the fetch function itself.
    """
    def __call__(
        self, 
        request: str, 
        /, 
        *, 
        signal: Any = None,
        fetcher: Any = None,
        **kwargs: Any
    ) -> Coroutine[Any, Any, FetchResponse]: ...
