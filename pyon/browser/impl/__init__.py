import sys
from collections.abc import Callable

from .._protocol import FFI, JS, AbortController
from .._protocol.http import Fetch

js: JS
ffi: FFI
fetch: Fetch
create_abort_controller: Callable[[], AbortController]

if sys.platform == "emscripten":
    from .pyodide_impl import PyodideFFI, PyodideJS
    from .pyodide_impl import create_abort_controller as pyodide_create_abort_controller
    js = PyodideJS()
    ffi = PyodideFFI()
    from pyodide.http import pyfetch as fetch

    create_abort_controller = pyodide_create_abort_controller
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

    from typing import Any
    async def mock_pyfetch(request: str, /, *, signal: Any = None, fetcher: Any = None, **kwargs: Any) -> Any:
        raise NotImplementedError("Browser environment not available")
    
    fetch = mock_pyfetch

    def mock_create_abort_controller():
        class MockAbortController:
            signal = None
            def abort(self):
                pass
        return MockAbortController()

    create_abort_controller = mock_create_abort_controller

__all__ = ["create_abort_controller", "fetch", "ffi", "js"]
