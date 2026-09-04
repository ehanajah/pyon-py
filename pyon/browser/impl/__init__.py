import sys
from .._protocol import JS, FFI
from .._protocol.http import Fetch

js: JS
ffi: FFI
fetch: Fetch

if sys.platform == "emscripten":
    from .pyodide_impl import PyodideJS, PyodideFFI
    js = PyodideJS()
    ffi = PyodideFFI()
    from pyodide.http import pyfetch as fetch
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

__all__ = ["js", "ffi", "fetch"]
