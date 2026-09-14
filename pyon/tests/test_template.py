import pytest
from pyon.core import Component, App, h

class ButtonComponent(Component):
    def render(self):
        return """
        <button class="{{ self.props.get('cls', 'btn') }}" on_click="self.props['on_click']">
            {{ self.props['text'] }}
        </button>
        """

class ListComponent(Component):
    def setup(self):
        self._state = {"items": ["A", "B", "C"]}
        
    def render(self):
        return """
        <ul>
            {% for item in self._state['items'] %}
                <li>{{ item }}</li>
            {% endfor %}
        </ul>
        """

class AppRoot(Component):
    def render(self):
        return """
        <div>
            <h1>Header</h1>
            <ListComponent />
            <ButtonComponent text="Click Me" on_click="lambda: None" />
        </div>
        """

def test_template_rendering():
    # Evaluate root
    app_root = AppRoot()
    vnode = app_root._render()
    
    assert vnode.tag == "div"
    assert len(vnode.children) == 3
    assert vnode.children[0].tag == "h1"
    assert vnode.children[0].children[0] == "Header"
    
    # Test sub-components are kept as class references
    list_comp = vnode.children[1]
    assert list_comp.tag == ListComponent
    
    btn_comp = vnode.children[2]
    assert btn_comp.tag == ButtonComponent
    assert btn_comp.props["text"] == "Click Me"

def test_template_for_loop():
    list_comp = ListComponent()
    list_comp.setup()
    vnode = list_comp._render()
    
    assert vnode.tag == "ul"
    assert len(vnode.children) == 3
    assert vnode.children[0].tag == "li"
    assert vnode.children[0].children[0] == "A"
    assert vnode.children[2].children[0] == "C"

