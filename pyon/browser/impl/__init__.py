import sys
from collections.abc import Callable
from typing import Any

from .._protocol import FFI, JS, AbortController
from .._protocol.http import (
    EventSourceAdapterProtocol,
    Fetch,
    WebSocketAdapterProtocol,
)

js: JS
ffi: FFI
fetch: Fetch
create_abort_controller: Callable[[], AbortController]
create_websocket_adapter: Callable[..., WebSocketAdapterProtocol]
create_eventsource_adapter: Callable[..., EventSourceAdapterProtocol]

if sys.platform == "emscripten":
    from .pyodide_impl import PyodideFFI, PyodideJS
    from .pyodide_impl import create_abort_controller as pyodide_create_abort_controller
    from .pyodide_impl import create_eventsource_adapter as pyodide_create_eventsource_adapter
    from .pyodide_impl import create_websocket_adapter as pyodide_create_websocket_adapter
    js = PyodideJS()
    ffi = PyodideFFI()
    from pyodide.http import pyfetch as fetch

    create_abort_controller = pyodide_create_abort_controller
    create_websocket_adapter = pyodide_create_websocket_adapter
    create_eventsource_adapter = pyodide_create_eventsource_adapter
else:
    class MockJS:
        document = None
        window = None
        JSON = None
        def queueMicrotask(self, callback):
            raise NotImplementedError("Browser environment not available")

    class MockFFI:
        def create_proxy(self, obj):
            return obj
        def to_js(self, obj, dict_converter=None):
            return obj

    js = MockJS() # type: ignore
    ffi = MockFFI() # type: ignore

    async def mock_pyfetch(request: str, /, *, signal: Any = None, fetcher: Any = None, **kwargs: Any) -> Any:
        raise NotImplementedError("Browser environment not available")
    
    fetch = mock_pyfetch

    def mock_create_abort_controller():
        class MockAbortController:
            signal = None
            def abort(self):
                pass
        return MockAbortController()

    def mock_create_websocket_adapter(url: str) -> Any:
        raise NotImplementedError("Browser environment not available")

    def mock_create_eventsource_adapter(url: str, with_credentials: bool = False) -> Any:
        raise NotImplementedError("Browser environment not available")

    create_abort_controller = mock_create_abort_controller
    create_websocket_adapter = mock_create_websocket_adapter  # type: ignore
    create_eventsource_adapter = mock_create_eventsource_adapter  # type: ignore

__all__ = [
    "create_abort_controller",
    "create_eventsource_adapter",
    "create_websocket_adapter",
    "fetch",
    "ffi",
    "js",
]
