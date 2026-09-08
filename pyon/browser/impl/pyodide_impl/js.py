from typing import Any

import js  # type: ignore[import]

from pyon.browser._protocol.dom import JS


class PyodideJS(JS):
    document = js.document # type: ignore
    window = js.window # type: ignore
    JSON = js.JSON # type: ignore
    
    def queueMicrotask(self, callback: Any) -> None:
        js.queueMicrotask(callback) # type: ignore
