import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, Generic, TypeVar

from pyon.core import Component

T = TypeVar("T")

class Resource(Generic[T]):
    """Reactive wrapper for asynchronous operations.
    Automatically triggers component re-render on state change.
    """
    def __init__(self, component: Component, fetcher: Callable[[], Coroutine[Any, Any, T]], lazy: bool = False) -> None:
        self._component = component
        self._fetcher = fetcher

        # Reactive state
        self.data: T | None = None
        self.error: Exception | None = None
        self.loading: bool = not lazy

        # Automatically execute fetcher after instantiation if not lazy
        if not lazy:
            self._execute()

    def _execute(self) -> None:
        self.loading = True
        self.error = None

        # Execute fetcher asynchronously
        asyncio.create_task(self._resolve())

    async def _resolve(self) -> None:
        try:
            self.data = await self._fetcher()
        except Exception as e:
            self.error = e
        finally:
            self.loading = False

            # Automatically trigger component re-render
            self._component.set_state({})

    def execute(self) -> None:
        """Manual trigger for refetching data."""
        self._execute()
        self._component.set_state({})

def create_resource(component: Component, fetcher: Callable[[], Coroutine[Any, Any, T]], lazy: bool = False) -> Resource[T]:
    return Resource(component, fetcher, lazy)
