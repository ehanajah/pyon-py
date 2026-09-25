from collections.abc import Callable
from typing import Any

import js  # type: ignore
from pyodide.ffi import create_proxy  # type: ignore

from pyon.browser._protocol.http import WebSocketAdapterProtocol  # type: ignore


class PyodideAbortController:
    def __init__(self):
        self._controller = js.AbortController.new() # type: ignore

    @property
    def signal(self):
        return self._controller.signal # type: ignore
    
    def abort(self):
        self._controller.abort() # type: ignore

def create_abort_controller():
    return PyodideAbortController()


class PyodideWebSocketAdapter:
    """Pyodide-specific WebSocket adapter.
    
    Wraps the browser's native WebSocket API via the ``js`` module.
    All Python callbacks are converted to JS proxies via ``create_proxy``
    and tracked in ``_proxies`` for cleanup in ``destroy()``.
    """

    def __init__(self, url: str):
        self._ws = js.WebSocket.new(url)  # type: ignore
        self._proxies: list[Any] = []

    @property
    def ready_state(self) -> int:
        return self._ws.readyState  # type: ignore

    def send(self, data: str) -> None:
        self._ws.send(data)  # type: ignore

    def close(self, code: int = 1000, reason: str = "") -> None:
        self._ws.close(code, reason)  # type: ignore

    def _set_callback(self, attr: str, callback: Callable[[Any], None]) -> None:
        proxy = create_proxy(callback)
        self._proxies.append(proxy)
        setattr(self._ws, attr, proxy)

    def set_on_open(self, callback: Callable[[], None]) -> None:
        self._set_callback("onopen", lambda e: callback())

    def set_on_message(self, callback: Callable[[Any], None]) -> None:
        self._set_callback("onmessage", callback)

    def set_on_close(self, callback: Callable[[Any], None]) -> None:
        self._set_callback("onclose", callback)

    def set_on_error(self, callback: Callable[[Any], None]) -> None:
        self._set_callback("onerror", callback)

    def destroy(self) -> None:
        try:
            self._ws.close()  # type: ignore
        except Exception:
            pass
        for p in self._proxies:
            p.destroy()
        self._proxies.clear()


class PyodideEventSourceAdapter:
    """Pyodide-specific Server-Sent Events (EventSource) adapter.
    
    Wraps the browser's native EventSource API via the ``js`` module.
    All Python callbacks are converted to JS proxies via ``create_proxy``
    and tracked in ``_proxies`` for cleanup in ``destroy()``.
    """

    def __init__(self, url: str, with_credentials: bool = False):
        options = js.Object.new()  # type: ignore
        options.withCredentials = with_credentials  # type: ignore
        self._es = js.EventSource.new(url, options)  # type: ignore
        self._proxies: list[Any] = []

    @property
    def ready_state(self) -> int:
        return self._es.readyState  # type: ignore

    def close(self) -> None:
        self._es.close()  # type: ignore

    def _set_callback(self, attr: str, callback: Callable[[Any], None]) -> None:
        proxy = create_proxy(callback)
        self._proxies.append(proxy)
        setattr(self._es, attr, proxy)

    def set_on_open(self, callback: Callable[[], None]) -> None:
        self._set_callback("onopen", lambda e: callback())

    def set_on_message(self, callback: Callable[[Any], None]) -> None:
        self._set_callback("onmessage", callback)

    def add_event_listener(self, event_name: str, callback: Callable[[Any], None]) -> None:
        proxy = create_proxy(callback)
        self._proxies.append(proxy)
        self._es.addEventListener(event_name, proxy)  # type: ignore

    def set_on_error(self, callback: Callable[[Any], None]) -> None:
        self._set_callback("onerror", callback)

    def destroy(self) -> None:
        try:
            self._es.close()  # type: ignore
        except Exception:
            pass
        for p in self._proxies:
            p.destroy()
        self._proxies.clear()


def create_websocket_adapter(url: str) -> PyodideWebSocketAdapter:
    return PyodideWebSocketAdapter(url)


def create_eventsource_adapter(url: str, with_credentials: bool = False) -> PyodideEventSourceAdapter:
    return PyodideEventSourceAdapter(url, with_credentials=with_credentials)