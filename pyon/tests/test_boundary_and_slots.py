import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


from pyon.core import App, BaseProps, Component, h


class ErrorProps(BaseProps):
    should_crash: bool

class BuggyComponent(Component[ErrorProps]):
    def render(self):
        if self.props.get("should_crash"):
            raise ValueError("Intentional Crash!")
        return h("div", {}, ["Safe"])

class BoundaryComponent(Component[BaseProps]):
    def setup(self):
        self._state = {"has_error": False, "error_msg": ""}

    def component_did_catch(self, error: Exception) -> None:
        self.set_state({"has_error": True, "error_msg": str(error)})

    def render(self):
        if self._state["has_error"]:
            return h("div", {"class": "error"}, [self._state["error_msg"]])
        # Render slot children
        children = self.props.get("children", [])
        return h("div", {"class": "boundary"}, children)

def test_error_boundary_and_slot_pattern():
    class RootComponent(Component):
        def render(self):
            return h(BoundaryComponent, {"key": "boundary"}, [
                h(BuggyComponent, {"key": "buggy", "should_crash": True})
            ])

    app = App(RootComponent)
    # Mock full_render because we just want to test internal tree expansion
    import sys
    sys.modules['pyon.dom'] = type('MockDOM', (), {'full_render': lambda *args, **kwargs: None, 'apply_patches': lambda *args, **kwargs: None, 'inject_scoped_css': lambda *args, **kwargs: None})()
    
    app.mount("#app")
    
    # Check that error was caught and fallback was rendered
    boundary_instance = app.component_map.get("RootComponent.boundary")
    assert boundary_instance is not None
    assert boundary_instance._state["has_error"] is True
    assert boundary_instance._state["error_msg"] == "Intentional Crash!"
    
    # Check that slot pattern works when no crash
    class RootComponentSafe(Component):
        def render(self):
            return h(BoundaryComponent, {"key": "boundary2"}, [
                h(BuggyComponent, {"key": "buggy2", "should_crash": False})
            ])

    app2 = App(RootComponentSafe)
    app2.mount("#app")
    boundary_instance2 = app2.component_map.get("RootComponentSafe.boundary2")
    assert boundary_instance2 is not None
    assert boundary_instance2.props.get("children") is not None
    assert len(boundary_instance2.props["children"]) == 1
    assert boundary_instance2.props["children"][0].tag == BuggyComponent
