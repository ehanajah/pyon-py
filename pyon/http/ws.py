"""WebSocket Client — platform-agnostic WebSocket API for Pyon-Py components.

This module provides a ``WebSocketClient`` class that wraps the platform-specific
WebSocket adapter (e.g., Pyodide's browser WebSocket) behind a clean Python API.

The client automatically integrates with the component lifecycle:
when the owning component is unmounted, the WebSocket connection is
closed and all JS proxies are destroyed to prevent memory leaks.

Usage example::

    from pyon.http.ws import WebSocketClient

    class ChatRoom(Component):
        def setup(self):
            self._state = {"messages": []}
            self.ws = WebSocketClient("wss://chat.example.com/room/1")
            self.ws.on_message(self.handle_message)

        def handle_message(self, event):
            msg = event.data
            self.set_state({"messages": [*self._state["messages"], msg]})

        def send_message(self, text):
            self.ws.send(text)
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from pyon.browser._protocol.http import WebSocketAdapterProtocol
from pyon.core import current_component


class WebSocketClient:
    """High-level WebSocket client with automatic lifecycle management.

    Args:
        url: The WebSocket server URL (e.g., ``wss://example.com/ws``).

    Attributes:
        url: The WebSocket server URL.
        CONNECTING: Ready state constant (0).
        OPEN: Ready state constant (1).
        CLOSING: Ready state constant (2).
        CLOSED: Ready state constant (3).
    """

    CONNECTING = 0
    OPEN = 1
    CLOSING = 2
    CLOSED = 3

    def __init__(self, url: str) -> None:
        from pyon.browser import create_websocket_adapter

        self.url = url
        self._adapter: WebSocketAdapterProtocol = create_websocket_adapter(url)

        # Register automatic cleanup when the owning component is unmounted
        comp = current_component.get()
        if comp is not None:
            comp._cleanups.append(self.close)

    @property
    def ready_state(self) -> int:
        """Current connection state (CONNECTING=0, OPEN=1, CLOSING=2, CLOSED=3)."""
        return self._adapter.ready_state

    def send(self, data: str | dict) -> None:
        """Send data through the WebSocket connection.
        
        Args:
            data: A string or dict. Dicts are automatically serialized to JSON.
        """
        if isinstance(data, dict):
            data = json.dumps(data)
        self._adapter.send(data)

    def on_open(self, callback: Callable[[], None]) -> None:
        """Register a callback for when the connection is established."""
        self._adapter.set_on_open(callback)

    def on_message(self, callback: Callable[[Any], None]) -> None:
        """Register a callback for incoming messages.
        
        The callback receives a MessageEvent object with a ``.data`` attribute
        containing the message payload.
        """
        self._adapter.set_on_message(callback)

    def on_close(self, callback: Callable[[Any], None]) -> None:
        """Register a callback for when the connection is closed.
        
        The callback receives a CloseEvent object with ``.code`` and ``.reason``
        attributes.
        """
        self._adapter.set_on_close(callback)

    def on_error(self, callback: Callable[[Any], None]) -> None:
        """Register a callback for connection errors."""
        self._adapter.set_on_error(callback)

    def close(self, code: int = 1000, reason: str = "") -> None:
        """Close the WebSocket connection and destroy all platform proxies.
        
        Args:
            code: WebSocket close code (default: 1000 = normal closure).
            reason: Human-readable close reason string.
        """
        self._adapter.destroy()
