from collections.abc import Callable
from typing import Any


class EventEmitter:
    def __init__(self) -> None:
        self._events: dict[str, set[Callable[..., Any]]] = {}

    def on(self, event: str, listener: Callable[..., Any]) -> Callable[[], None]:
        """Subscribe to an event. Returns off() function."""
        if event not in self._events:
            self._events[event] = set()

        self._events[event].add(listener)

        def off() -> None:
            self.off(event, listener)

        return off

    def off(self, event: str, listener: Callable[..., Any]) -> None:
        """Unsubscribe from an event."""
        if event in self._events:
            self._events[event].discard(listener)
            if not self._events[event]:
                del self._events[event]

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event with payload."""
        if event in self._events:
            for listener in list(self._events[event]):
                listener(*args, **kwargs)
                