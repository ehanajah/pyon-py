from collections.abc import Callable
from typing import Any

from pyon.browser import ffi, js


def queue_microtask(callback: "Callable[[], None]") -> None:
    """Queues a callback to be executed asynchronously in the browser.

    This function is a wrapper around ``js.queueMicrotask()`` that
    destroys the callback's JS Proxy after execution.

    Args:
        callback: The function to be executed asynchronously.
    """
    proxy: Any = None
    def wrapped() -> None:
        try:
            callback()
        finally:
            if proxy is not None and hasattr(proxy, "destroy"):
                proxy.destroy()

    proxy = ffi.create_proxy(wrapped)
    js.queueMicrotask(proxy)