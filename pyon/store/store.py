from collections.abc import Callable
from typing import Any


class Store:
    _listeners: set[Callable[[], None]]

    def __init__(self) -> None:
        # Use super().__setattr__ to prevent self __setattr__ interceptor 
        super().__setattr__("_listeners", set())

    def subscribe(self, listener: Callable[[], None]) -> Callable[[], None]:
        """
        Register callback to be called when the store is updated.
        """
        self._listeners.add(listener)

        def unsubscribe() -> None:
            self._listeners.remove(listener)

        return unsubscribe

    def notify(self) -> None:
        """
        Publish the store's state to all subscribers.
        Call this method manually ONLY IF you are mutating the deeply nested object
        (like `self.list.append(1)`).
        """
        for listener in list(self._listeners):
            listener()

    def __setattr__(self, key: str, value: Any) -> None:
        """
        Interceptor for object attribute mutation.
        """
        super().__setattr__(key, value)

        if not key.startswith("_"):
            self.notify()
