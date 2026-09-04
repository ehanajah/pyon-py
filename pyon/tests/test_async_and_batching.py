"""
Tests for Coroutine Dispatcher, Microtask Batching, and Stale Unmount Protection.
"""
import sys
import asyncio
from pathlib import Path
from typing import Optional
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Mock dom so tests can execute without browser DOM / Pyodide runtime
sys.modules['pyon.dom'] = type('MockDOM', (), {
    'full_render': lambda *args, **kwargs: None,
    'apply_patches': lambda *args, **kwargs: None
})()

from pyon.core import App
from pyon.core import Component
from pyon.core import h


def test_async_lifecycle_on_mount() -> None:
    """Verifies that an async on_mount hook is dispatched cleanly without blocking initial mount,

    and automatically flushes updates when the background coroutine completes.
    """
    class AsyncLoader(Component):
        def __init__(self, props: Optional[dict] = None) -> None:
            super().__init__(props)
            self._state = {"text": "loading"}

        async def on_mount(self) -> None:
            # Simulate waiting for an asynchronous task or network fetch
            await asyncio.sleep(0.01)
            self.set_state({"text": "loaded!"})

        def render(self):
            return h("div", {}, [self._state["text"]])

    class Root(Component):
        def render(self):
            return h(AsyncLoader, {"key": "loader"})

    async def run_test() -> None:
        app = App(Root)
        app.mount("#app")

        loader = app.component_map.get("Root.loader")
        assert loader is not None

        # 1. Immediately after mount (before await resolves), initial render state is present
        assert loader._state["text"] == "loading"

        # 2. Yield control back to the event loop so the background coroutine completes
        await asyncio.sleep(0.05)

        # 3. State should automatically be updated and batched without manual flushing
        assert loader._state["text"] == "loaded!"

    asyncio.run(run_test())


def test_microtask_batching_in_loop() -> None:
    """Verifies that multiple synchronous state updates inside an active Event Loop are

    batched into a single scheduled flush when the call stack clears.
    """
    class Batcher(Component):
        def __init__(self, props: Optional[dict] = None) -> None:
            super().__init__(props)
            self._state = {"count": 0}

        def do_spam_update(self) -> None:
            self.set_state({"count": 10})
            self.set_state({"count": 20})
            self.set_state({"count": 30})

        def render(self):
            return h("span", {}, [str(self._state["count"])])

    class Root(Component):
        def render(self):
            return h(Batcher, {"key": "batcher"})

    async def run_test() -> None:
        app = App(Root)
        app.mount("#app")

        batcher = app.component_map.get("Root.batcher")
        assert batcher is not None

        # Trigger multiple sequential state updates within the same call stack
        batcher.do_spam_update()

        # 1. Before yielding to the loop, updates are queued once (deduplicated by _dirty flag) and flush is scheduled
        assert app._flush_scheduled is True
        assert len(app.dirty_components) == 1
        assert batcher._state["count"] == 0

        # 2. Clear the call stack by yielding execution to the event loop
        await asyncio.sleep(0)

        # 3. Updates are processed completely in a single batched flush
        assert len(app.dirty_components) == 0
        assert app._flush_scheduled is False
        assert batcher._state["count"] == 30

    asyncio.run(run_test())


def test_stale_unmount_guard() -> None:
    """Verifies that calling set_state on an unmounted component is ignored,

    preventing memory leaks or errors from delayed asynchronous responses.
    """
    class Dummy(Component):
        def __init__(self, props: Optional[dict] = None) -> None:
            super().__init__(props)
            self._state = {"alive": True}

        def render(self):
            return h("div")

    comp = Dummy()
    comp._mounted = True  # Simulate active mounted component

    # Simulate component unmount (e.g. removed from DOM during reconciliation)
    comp._invoke_on_unmount()
    assert comp._mounted is False

    # Attempt to call set_state on the unmounted instance
    comp.set_state({"alive": False})

    # Guard should immediately block the update
    assert comp._dirty is False
    assert comp._state["alive"] is True
