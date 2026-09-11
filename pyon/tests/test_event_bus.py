import pytest
from pyon.core.bus import EventEmitter
from pyon.core import Component, App, h

def test_event_emitter_basic():
    bus = EventEmitter()
    received = []
    
    def on_hello(msg):
        received.append(msg)
        
    unsub = bus.on("HELLO", on_hello)
    bus.emit("HELLO", "World")
    assert received == ["World"]
    
    unsub()
    bus.emit("HELLO", "Again")
    assert len(received) == 1

def test_component_use_event_cleanup():
    bus = EventEmitter()
    
    class Listener(Component):
        def setup(self):
            self.use_event(bus, "PING", self.handle_ping)
            
        def handle_ping(self):
            pass
            
        def render(self):
            return h("div", {}, ["Listener"])
            
    class Parent(Component):
        def setup(self):
            self._state = {"show": True}
            
        def toggle(self):
            self._state["show"] = False
            self.set_state(self._state)
            
        def render(self):
            if self._state["show"]:
                return h(Listener, {"key": "child"})
            return h("div", {"key": "empty"})

    app = App(Parent)
    import sys
    sys.modules['pyon.dom'] = type('MockDOM', (), {
        'full_render': lambda *args, **kwargs: None, 
        'apply_patches': lambda *args, **kwargs: None,
        'inject_scoped_css': lambda *args, **kwargs: None
    })()
    
    app.mount("#app")
    
    # After mount, there should be one listener
    assert "PING" in bus._events
    assert len(bus._events["PING"]) == 1
    
    # Toggle parent to hide Child (will trigger unmount)
    parent_instance = list(app.component_map.values())[0]
    parent_instance.toggle()
    app.flush_updates()
    
    # After unmount, the cleanup should have fired, removing the listener
    assert "PING" not in bus._events or len(bus._events["PING"]) == 0

