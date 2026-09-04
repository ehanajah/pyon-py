import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Callable, Any
from pyon.core import Component, BaseProps
from pyon.core import h
import pytest

class MyCustomProps(BaseProps):
    title: str
    on_click: Callable[[int], None]

class MyComponent(Component[MyCustomProps]):
    def render(self):
        # Memastikan props dapat diakses dan type checker tidak komplain (saat static analysis)
        title = self.props.get("title", "default")
        
        # Helper fungsi internal untuk event
        def handle_click(e: Any) -> None:
            if "on_click" in self.props:
                self.props["on_click"](42)

        return h("button", {"onClick": handle_click}, [title])

def test_base_props_can_be_instantiated_with_events():
    # Test bahwa custom props bisa di-pass dan diakses dengan benar pada saat runtime
    events_called = []
    
    def my_click_handler(val: int) -> None:
        events_called.append(val)
        
    props: MyCustomProps = {
        "key": "test-1",
        "title": "Click Me",
        "on_click": my_click_handler
    }
    
    comp = MyComponent(props)
    
    # Render component
    vnode = comp.render()
    assert vnode.tag == "button"
    assert vnode.children[0] == "Click Me"
    
    # Panggil event secara manual
    click_handler = vnode.props["onClick"]
    click_handler(None)
    
    # Pastikan event terpanggil dengan payload yang benar
    assert len(events_called) == 1
    assert events_called[0] == 42
