from collections.abc import Callable, Coroutine
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


class WebSocketAdapterProtocol(Protocol):
    """Protocol for platform-agnostic WebSocket adapter implementations.

    Implementors must provide methods for sending/receiving messages,
    managing connection lifecycle, and registering event callbacks.
    All JS/platform-specific details are hidden behind this interface.
    """
    @property
    def ready_state(self) -> int:
        """Connection state: 0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED."""
        ...

    def send(self, data: str) -> None: ...
    def close(self, code: int = 1000, reason: str = "") -> None: ...
    def set_on_open(self, callback: Callable[[], None]) -> None: ...
    def set_on_message(self, callback: Callable[[Any], None]) -> None: ...
    def set_on_close(self, callback: Callable[[Any], None]) -> None: ...
    def set_on_error(self, callback: Callable[[Any], None]) -> None: ...
    def destroy(self) -> None:
        """Close connection and destroy all platform proxies to prevent memory leaks."""
        ...


class EventSourceAdapterProtocol(Protocol):
    """Protocol for platform-agnostic Server-Sent Events (SSE) adapter implementations.

    Implementors must provide methods for listening to server-pushed events,
    managing connection lifecycle, and registering event callbacks.
    All JS/platform-specific details are hidden behind this interface.
    """
    @property
    def ready_state(self) -> int:
        """Connection state: 0=CONNECTING, 1=OPEN, 2=CLOSED."""
        ...

    def close(self) -> None: ...
    def set_on_open(self, callback: Callable[[], None]) -> None: ...
    def set_on_message(self, callback: Callable[[Any], None]) -> None: ...
    def add_event_listener(self, event_name: str, callback: Callable[[Any], None]) -> None: ...
    def set_on_error(self, callback: Callable[[Any], None]) -> None: ...
    def destroy(self) -> None:
        """Close connection and destroy all platform proxies to prevent memory leaks."""
        ...

    