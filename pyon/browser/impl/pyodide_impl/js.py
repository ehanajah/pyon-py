from typing import Any

from pyon.browser._protocol.dom import JS
import js  # type: ignore[import]

class PyodideJS(JS):
    document = js.document # type: ignore
    window = js.window # type: ignore
    JSON = js.JSON # type: ignore
    
    def queueMicrotask(self, callback: Any) -> None:
        js.queueMicrotask(callback) # type: ignore
