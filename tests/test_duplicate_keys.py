import pytest
from pyon.core.component import Component
from pyon.core.app import App, ErrorCaughtByBoundary

class DummyCard(Component):
    def render(self):
        return "<div>card</div>"

class AppCollision(Component):
    def render(self):
        return """
        <div>
            <div>
                <DummyCard key="card-1" />
            </div>
            <div>
                <DummyCard key="card-1" />
            </div>
        </div>
        """

class AppNoCollision(Component):
    def render(self):
        return """
        <div>
            <div>
                <DummyCard key="card-1" />
            </div>
            <div>
                <DummyCard key="card-2" />
            </div>
        </div>
        """

def test_duplicate_key_collision():
    app = App(AppCollision)
    
    with pytest.raises(ValueError, match="Duplicate component key 'AppCollision.card-1' detected"):
        # We don't mount because it requires DOM, but we can trigger _expand_tree directly.
        # But wait, app.mount requires DOM, so we can just run _expand_tree manually.
        from pyon.core.vnode import VNode
        from pyon.core.app import _expand_tree
        
        root_node = VNode(
            tag=app.root_class,
            props={"key": app.root_class.__name__},
            children=[],
        )
        _expand_tree(
            root_node,
            path="0",
            parent_key="",
            component_map=app.component_map,
            app=app,
        )

def test_no_duplicate_key_collision():
    app = App(AppNoCollision)
    from pyon.core.vnode import VNode
    from pyon.core.app import _expand_tree
    
    root_node = VNode(
        tag=app.root_class,
        props={"key": app.root_class.__name__},
        children=[],
    )
    # This should not raise any exceptions
    expanded = _expand_tree(
        root_node,
        path="0",
        parent_key="",
        component_map=app.component_map,
        app=app,
    )
    
    # 3 instances should be in component map (AppNoCollision, DummyCard 1, DummyCard 2)
    assert len(app.component_map) == 3
