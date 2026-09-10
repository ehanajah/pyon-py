import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pyon.core import App, Component, h
from pyon.core.css import CSSManager


class MyComponent(Component):
    styles = """
    .btn { color: red; }
    """
    def render(self):
        return h("button", {"class": "btn"}, ["Click Me"])

class ChildComp(Component):
    def render(self):
        return h("div", {"class": "child"}, ["Child"])

class ParentComp(Component):
    styles = """
    .parent { color: blue; }
    """
    def render(self):
        return h("div", {"class": "parent"}, [
            h(ChildComp, {})
        ])

def test_css_scoping():
    # Verify CSSManager registered the scopes
    registry = CSSManager.get_all()
    assert MyComponent.scope_id in registry
    assert ParentComp.scope_id in registry
    assert "color: red" in registry[MyComponent.scope_id]
    
    # Mock dom
    import sys
    sys.modules['pyon.dom'] = type('MockDOM', (), {
        'full_render': lambda *args, **kwargs: None, 
        'apply_patches': lambda *args, **kwargs: None,
        'inject_scoped_css': lambda *args, **kwargs: None
    })()

    app = App(ParentComp)
    app.mount("#app")

    # Verify props propagation
    parent_vnode = app.current_tree
    assert parent_vnode.tag == "div"
    assert f"data-{ParentComp.scope_id}" in parent_vnode.props
    
    # Verify penetration to child
    child_vnode = parent_vnode.children[0]
    assert child_vnode.tag == "div"
    # Child component's root should have its parent's scope_id
    assert f"data-{ParentComp.scope_id}" in child_vnode.props

if __name__ == "__main__":
    test_css_scoping()
    print("CSS Scoping tests passed!")
