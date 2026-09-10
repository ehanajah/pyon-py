import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from pyon.core import Component, BaseProps
from pyon.core import h
from pyon.core import App

# Mock dom so tests can execute without browser DOM / Pyodide runtime
sys.modules['pyon.dom'] = type('MockDOM', (), {
    'full_render': lambda *args, **kwargs: None,
    'apply_patches': lambda *args, **kwargs: None, 'inject_scoped_css': lambda *args, **kwargs: None
})()


# ── TEST 1: Basic Provide / Inject ──────────────────────────────────────────
def test_basic_provide_inject():
    class Leaf(Component):
        def render(self):
            theme = self.inject("theme")
            font = self.inject("font_size")
            return h("span", {"class": f"theme-{theme}"}, [f"Font: {font}"])

    class Root(Component):
        def setup(self):
            self.provide("theme", "dark")
            self.provide("font_size", 16)

        def render(self):
            return h("div", {}, [
                h(Leaf, {"key": "leaf"})
            ])

    app = App(Root)
    app.mount("#app")

    leaf_instance = app.component_map.get("Root.leaf")
    assert leaf_instance is not None
    assert leaf_instance.inject("theme") == "dark"
    assert leaf_instance.inject("font_size") == 16


# ── TEST 2: Inject Default Fallback ──────────────────────────────────────────
def test_inject_default_fallback():
    class Child(Component):
        def render(self):
            val = self.inject("missing_key", default="fallback_value")
            return h("div", {}, [val])

    class Root(Component):
        def render(self):
            return h("div", {}, [
                h(Child, {"key": "child"})
            ])

    app = App(Root)
    app.mount("#app")

    child = app.component_map.get("Root.child")
    assert child is not None
    assert child.inject("missing_key", default="fallback_value") == "fallback_value"


# ── TEST 3: Hierarchical Scoping & Overriding (Isolation) ─────────────────────
def test_context_hierarchy_and_overriding():
    class Leaf(Component):
        def render(self):
            color = self.inject("color")
            return h("div", {"class": color}, [color])

    class BranchA(Component):
        def setup(self):
            # Override context in this branch
            self.provide("color", "red")

        def render(self):
            return h("section", {}, [h(Leaf, {"key": "leafA"})])

    class BranchB(Component):
        # Does not override color; should inherit "blue" from Root
        def render(self):
            return h("section", {}, [h(Leaf, {"key": "leafB"})])

    class Root(Component):
        def setup(self):
            self.provide("color", "blue")

        def render(self):
            return h("div", {}, [
                h(BranchA, {"key": "branchA"}),
                h(BranchB, {"key": "branchB"})
            ])

    app = App(Root)
    app.mount("#app")

    leaf_a = app.component_map.get("Root.branchA.leafA")
    leaf_b = app.component_map.get("Root.branchB.leafB")

    assert leaf_a is not None
    assert leaf_b is not None
    # Verify exact tree-scoped isolation
    assert leaf_a.inject("color") == "red"
    assert leaf_b.inject("color") == "blue"
    # Ensure Root context remained unpolluted by BranchA
    assert app.component_map["Root"]._contexts["color"] == "blue"


# ── TEST 4: Reactive Context via Injected Updater Callback ───────────────────
def test_reactive_context_via_callback():
    class Switcher(Component):
        def render(self):
            theme_fn = self.inject("get_theme")
            toggle_fn = self.inject("toggle_theme")
            return h("button", {"on_click": toggle_fn}, [theme_fn()])

    class Root(Component):
        def setup(self):
            self._state = {"theme": "dark"}
            self.provide("get_theme", lambda: self._state["theme"])
            self.provide("toggle_theme", self.toggle)

        def toggle(self):
            new_val = "light" if self._state["theme"] == "dark" else "dark"
            self.set_state({"theme": new_val})

        def render(self):
            return h("div", {}, [h(Switcher, {"key": "switcher"})])

    app = App(Root)
    app.mount("#app")

    switcher = app.component_map.get("Root.switcher")
    assert switcher is not None
    assert switcher.inject("get_theme")() == "dark"

    # Simulate triggering the injected toggle callback
    switcher.inject("toggle_theme")()
    # At this point, update is in dirty queue
    assert len(app.dirty_components) == 1

    # Flush updates to apply reactivity across the subtree
    app.flush_updates()
    assert switcher.inject("get_theme")() == "light"


# ── TEST 5: Batching Multiple State Updates ─────────────────────────────────
def test_state_batching_update_system():
    class Counter(Component):
        def setup(self):
            self._state = {"count": 0, "status": "idle"}

        def do_triple_update(self):
            self.set_state({"count": 1})
            self.set_state({"count": 2})
            self.set_state({"status": "active", "count": 3})

        def render(self):
            return h("div", {}, [f"{self._state['count']}-{self._state['status']}"])

    class Root(Component):
        def render(self):
            return h(Counter, {"key": "counter"})

    app = App(Root)
    app.mount("#app")

    counter = app.component_map.get("Root.counter")
    assert counter is not None

    # Trigger multiple synchronous state updates
    counter.do_triple_update()

    # Before flush, state has not been mutated directly, and component is queued once!
    assert counter._state["count"] == 0
    assert len(counter._updates) == 3
    assert counter._dirty is True
    assert len(app.dirty_components) == 1

    # Execute batch update
    app.flush_updates()

    # All updates applied in order, state is updated cleanly
    assert counter._state["count"] == 3
    assert counter._state["status"] == "active"
    assert counter._dirty is False
    assert len(app.dirty_components) == 0


# ── TEST 6: Circuit Breaker for Infinite Re-render Loop ──────────────────────
def test_circuit_breaker_infinite_loop():
    class Looper(Component):
        def setup(self):
            self._state = {"tick": 0}

        def on_update(self, prev_props, prev_state):
            # BUG: Unconditional setState inside on_update triggers infinite re-renders!
            self.set_state({"tick": self._state["tick"] + 1})

        def render(self):
            return h("div", {}, [f"Tick: {self._state['tick']}"])

    class Root(Component):
        def render(self):
            return h(Looper, {"key": "looper"})

    app = App(Root)
    app.mount("#app")

    looper = app.component_map.get("Root.looper")
    # Trigger initial update to start the infinite ping-pong cycle
    looper.set_state({"tick": 1})

    with pytest.raises(RuntimeError, match="Maximum update depth exceeded"):
        app.flush_updates()

    # Queue should be cleaned up by circuit breaker
    assert len(app.dirty_components) == 0


# ── TEST 7: Lifecycle on_update with Historical Snapshots ───────────────────
def test_on_update_prev_props_and_prev_state_snapshot():
    history = []

    class Tracker(Component):
        def setup(self):
            self._state = {"val": 10}

        def on_update(self, prev_props, prev_state):
            history.append({
                "prev_state": dict(prev_state),
                "curr_state": dict(self._state)
            })

        def render(self):
            return h("span", {}, [str(self._state["val"])])

    class Root(Component):
        def render(self):
            return h(Tracker, {"key": "tracker"})

    app = App(Root)
    app.mount("#app")

    tracker = app.component_map.get("Root.tracker")
    tracker.set_state({"val": 20})
    app.flush_updates()

    tracker.set_state({"val": 30})
    app.flush_updates()

    assert len(history) == 2
    assert history[0]["prev_state"] == {"val": 10}
    assert history[0]["curr_state"] == {"val": 20}

    assert history[1]["prev_state"] == {"val": 20}
    assert history[1]["curr_state"] == {"val": 30}


# ── TEST 8: Global App Context Provide and Hierarchy Override ─────────────────
def test_global_app_context_provide_and_override():
    class Leaf(Component):
        def render(self):
            app_name = self.inject("app_name")
            api_url = self.inject("api_url")
            return h("span", {}, [f"{app_name}:{api_url}"])

    class CustomBranch(Component):
        def setup(self):
            # Override api_url specifically for this branch
            self.provide("api_url", "https://staging.test")

        def render(self):
            return h("div", {}, [h(Leaf, {"key": "custom_leaf"})])

    class DefaultBranch(Component):
        # Does not override; inherits directly from App's global context via Root
        def render(self):
            return h("div", {}, [h(Leaf, {"key": "default_leaf"})])

    class Root(Component):
        def render(self):
            return h("main", {}, [
                h(CustomBranch, {"key": "custom_branch"}),
                h(DefaultBranch, {"key": "default_branch"})
            ])

    app = App(Root)
    # Provide global context directly at App level before mount
    app.provide("app_name", "PyOn-App")
    app.provide("api_url", "https://production.test")

    app.mount("#app")

    custom_leaf = app.component_map.get("Root.custom_branch.custom_leaf")
    default_leaf = app.component_map.get("Root.default_branch.default_leaf")

    assert custom_leaf is not None
    assert default_leaf is not None

    # Both leaves should inherit the global app_name
    assert custom_leaf.inject("app_name") == "PyOn-App"
    assert default_leaf.inject("app_name") == "PyOn-App"

    # Default leaf gets production URL from global app context
    assert default_leaf.inject("api_url") == "https://production.test"
    # Custom leaf gets overridden staging URL from CustomBranch
    assert custom_leaf.inject("api_url") == "https://staging.test"
    # Global context on app remains unpolluted
    assert app._contexts["api_url"] == "https://production.test"

