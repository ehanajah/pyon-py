from typing import Any, Callable

from pyon.browser._protocol.ffi import FFI, FFIProxy
from pyodide.ffi import create_proxy, to_js  # type: ignore[import]

class PyodideFFI(FFI):
    def create_proxy(self, obj: Callable[..., Any]) -> FFIProxy:
        return create_proxy(obj)

    def to_js(self, obj: Any, dict_converter: Any = ...) -> Any:
        return to_js(obj, dict_converter=dict_converter)