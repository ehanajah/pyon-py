import pytest
from pyon.store import Store
from pyon.core import Component, App, h

def test_store_initialization_and_notify():
    class CounterStore(Store):
        count = 0
        def increment(self):
            self.count += 1
            
    store = CounterStore()
    
    updates = 0
    def listener():
        nonlocal updates
        updates += 1
        
    unsubscribe = store.subscribe(listener)
    
    # Trigger mutation
    store.increment()
    assert store.count == 1
    assert updates == 1
    
    # Test unsubscribe
    unsubscribe()
    store.increment()
    assert store.count == 2
    assert updates == 1

def test_component_use_store_and_unmount_cleanup():
    class TestStore(Store):
        val = 10
        
    global_store = TestStore()
    
    class Child(Component):
        def setup(self):
            self.store = self.use_store(global_store)
            
        def render(self):
            return h("div", {}, [str(self.store.val)])
            
    class Parent(Component):
        def setup(self):
            self._state = {"show": True}
            
        def toggle(self):
            self._state["show"] = False
            self.set_state(self._state)
            
        def render(self):
            if self._state["show"]:
                return h(Child, {"key": "child"})
            return h("div", {"key": "empty"})

    app = App(Parent)
    import sys
    sys.modules['pyon.dom'] = type('MockDOM', (), {
        'full_render': lambda *args, **kwargs: None, 
        'apply_patches': lambda *args, **kwargs: None,
        'inject_scoped_css': lambda *args, **kwargs: None
    })()
    
    app.mount("#app")
    
    # Initially, 1 listener should be registered (the Child component)
    assert len(global_store._listeners) == 1
    
    # Toggle parent to hide Child (will trigger unmount)
    parent_instance = list(app.component_map.values())[0]
    parent_instance.toggle()
    app.flush_updates()
    
    # After unmount, the cleanup should have fired, removing the listener
    assert len(global_store._listeners) == 0

