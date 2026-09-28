"""EventSource Client — platform-agnostic Server-Sent Events (SSE) API for Pyon-Py.

This module provides an ``EventSourceClient`` class that wraps the platform-specific
EventSource adapter (e.g., Pyodide's browser EventSource) behind a clean Python API.

The client automatically integrates with the component lifecycle:
when the owning component is unmounted, the EventSource connection is
closed and all JS proxies are destroyed to prevent memory leaks.

Usage example::

    from pyon.http.sse import EventSourceClient

    class StockTicker(Component):
        def setup(self):
            self._state = {"price": 0}
            self.sse = EventSourceClient("https://api.example.com/stream/prices")
            self.sse.on_message(self.handle_update)

            # Listen to custom named events
            self.sse.on("price_update", self.handle_price)

        def handle_update(self, event):
            data = event.data
            self.set_state({"price": data})
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pyon.browser._protocol.http import EventSourceAdapterProtocol
from pyon.core import current_component


class EventSourceClient:
    """High-level Server-Sent Events (SSE) client with automatic lifecycle management.

    Args:
        url: The SSE server endpoint URL.
        with_credentials: Whether to include credentials (cookies) in cross-origin
            requests. Defaults to ``False``.

    Attributes:
        url: The SSE server endpoint URL.
        CONNECTING: Ready state constant (0).
        OPEN: Ready state constant (1).
        CLOSED: Ready state constant (2).
    """

    CONNECTING = 0
    OPEN = 1
    CLOSED = 2

    def __init__(self, url: str, with_credentials: bool = False) -> None:
        from pyon.browser.impl import create_eventsource_adapter

        self.url = url
        self._adapter: EventSourceAdapterProtocol = create_eventsource_adapter(
            url, with_credentials=with_credentials
        )

        # Register automatic cleanup when the owning component is unmounted
        comp = current_component.get()
        if comp is not None:
            comp._cleanups.append(self.close)

    @property
    def ready_state(self) -> int:
        """Current connection state (CONNECTING=0, OPEN=1, CLOSED=2)."""
        return self._adapter.ready_state

    def on_open(self, callback: Callable[[], None]) -> None:
        """Register a callback for when the connection is established."""
        self._adapter.set_on_open(callback)

    def on_message(self, callback: Callable[[Any], None]) -> None:
        """Register a callback for incoming messages (unnamed events).
        
        The callback receives a MessageEvent object with a ``.data`` attribute
        containing the message payload.
        """
        self._adapter.set_on_message(callback)

    def on(self, event_name: str, callback: Callable[[Any], None]) -> None:
        """Register a callback for a specific named event type.

        SSE servers can send named events (``event: price_update``).
        Use this method to listen for those specific event types.

        Args:
            event_name: The event type name to listen for.
            callback: Function to call when the event is received.
        """
        self._adapter.add_event_listener(event_name, callback)

    def on_error(self, callback: Callable[[Any], None]) -> None:
        """Register a callback for connection errors."""
        self._adapter.set_on_error(callback)

    def close(self) -> None:
        """Close the EventSource connection and destroy all platform proxies."""
        self._adapter.destroy()
