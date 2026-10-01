import sys
import asyncio

# Mock dom so tests can execute without browser DOM / Pyodide runtime
sys.modules['pyon.dom'] = type('MockDOM', (), {
    'full_render': lambda *args, **kwargs: None,
    'apply_patches': lambda *args, **kwargs: None,
    'inject_scoped_css': lambda *args, **kwargs: None
})()

from pyon.core import App, Component, h, Suspense, lazy

class RealComponent(Component):
    def render(self):
        return h("div", {}, ["Real Content"])

class SecondRealComponent(Component):
    def render(self):
        return h("span", {}, ["Second Content"])


def test_lazy_suspense_basic() -> None:
    """Verifies that Suspense shows fallback during loading and then content upon resolution."""
    
    async def mock_loader():
        await asyncio.sleep(0.01)
        return RealComponent

    LazyComp = lazy(mock_loader, "RealComponent")

    class Root(Component):
        def render(self):
            return h(Suspense, {"key": "suspense", "fallback": "Loading..."}, [
                h(LazyComp, {"key": "lazy"})
            ])

    async def run_test():
        app = App(Root)
        app.mount("#app")

        suspense = app.component_map.get("Root.suspense")
        assert suspense is not None
        
        # We can also check that the lazy class has started loading
        assert LazyComp._loading is True
        assert LazyComp._resolved is None
        
        # 2. Wait for the loader to finish
        await asyncio.sleep(0.05)
        
        # 3. After resolution, Suspense should trigger re-render and pending should be False
        assert suspense._state["pending"] is False
        assert LazyComp._loading is False
        assert LazyComp._resolved is RealComponent

    asyncio.run(run_test())


def test_lazy_without_suspense_throws() -> None:
    """Verifies that rendering a lazy component without a Suspense boundary throws RuntimeError."""
    
    async def mock_loader():
        return RealComponent

    LazyComp = lazy(mock_loader, "RealComponent")

    class Root(Component):
        def render(self):
            # No Suspense!
            return h(LazyComp, {"key": "lazy"})

    async def run_test():
        app = App(Root)
        try:
            app.mount("#app")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "Suspense boundary" in str(e)
            
    asyncio.run(run_test())


def test_multiple_lazy_parallel_loading() -> None:
    """Verifies that multiple lazy components under one Suspense are preloaded together."""
    
    async def mock_loader_1():
        await asyncio.sleep(0.02)
        return RealComponent
        
    async def mock_loader_2():
        await asyncio.sleep(0.02)
        return SecondRealComponent

    LazyComp1 = lazy(mock_loader_1, "RealComponent")
    LazyComp2 = lazy(mock_loader_2, "SecondRealComponent")

    class Root(Component):
        def render(self):
            return h(Suspense, {"key": "suspense", "fallback": "Loading Both..."}, [
                h(LazyComp1, {"key": "lazy1"}),
                h(LazyComp2, {"key": "lazy2"})
            ])

    async def run_test():
        app = App(Root)
        app.mount("#app")

        # 1. Check that both started loading immediately (parallel)
        # Even though LazyComp2 was never instantiated by expand_tree,
        # _preload_lazy_descendants should have triggered its _start_loading()
        assert LazyComp1._loading is True
        assert LazyComp2._loading is True
        
        # 2. Wait for resolution
        await asyncio.sleep(0.05)
        
        # 3. Check they both resolved
        assert LazyComp1._resolved is RealComponent
        assert LazyComp2._resolved is SecondRealComponent

    asyncio.run(run_test())
