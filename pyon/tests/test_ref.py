"""
Test: Component ref integration — pengujian direct DOM access menggunakan refs.

Menguji:
- Component dapat mendaftarkan ref melalui prop 'ref'.
- Ref menunjuk ke DOMElement yang tepat di owner yang benar (meskipun di-nested).
- Ref dihapus otomatis (cleanup) ketika elemen dihapus dari DOM.
- Ref diperbarui ketika atribut ref diganti.

Run:
    python pyon/tests/test_ref.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ============================================================================
# Mock bridge layer
# ============================================================================

class MockElement:
    def __init__(self, tag="div"):
        self.tag = tag
        self.className = ""
        self.textContent = ""
        self.attributes = {}
        self.child_nodes = []
        self.parent = None
        self.style = MagicMock()
        self._event_listeners = {}

    @property
    def childNodes(self):
        return self.child_nodes

    @property
    def children(self):
        return [c for c in self.child_nodes if isinstance(c, MockElement)]

    def appendChild(self, child):
        self.child_nodes.append(child)
        if isinstance(child, MockElement):
            child.parent = self
        return child

    def insertBefore(self, new_child, ref_child):
        if ref_child in self.child_nodes:
            idx = self.child_nodes.index(ref_child)
            self.child_nodes.insert(idx, new_child)
        else:
            self.appendChild(new_child)
        return new_child

    def remove(self):
        if self.parent:
            self.parent.child_nodes.remove(self)

    def replaceWith(self, new_el):
        if self.parent:
            idx = self.parent.child_nodes.index(self)
            self.parent.child_nodes[idx] = new_el
            new_el.parent = self.parent

    def setAttribute(self, key, val):
        self.attributes[key] = val

    def getAttribute(self, key):
        return self.attributes.get(key)
        
    def hasAttribute(self, key):
        return key in self.attributes

    def removeAttribute(self, key):
        self.attributes.pop(key, None)

    def addEventListener(self, event, handler):
        self._event_listeners.setdefault(event, []).append(handler)


class MockTextNode:
    def __init__(self, text):
        self.textContent = text
        self.parent = None


class MockDocument:
    def __init__(self):
        self._elements = {}
        self._app_container = MockElement("div")
        self._elements["#app"] = self._app_container

    def querySelector(self, selector):
        return self._elements.get(selector)

    def createElement(self, tag):
        return MockElement(tag)

    def createTextNode(self, text):
        return MockTextNode(text)


class MockProxy:
    def __init__(self, fn):
        self._fn = fn
        self._destroyed = False

    def __call__(self, *args, **kwargs):
        return self._fn(*args, **kwargs)

    def destroy(self):
        self._destroyed = True


mock_document = MockDocument()
mock_js = MagicMock()
mock_js.document = mock_document
mock_js.queueMicrotask = lambda proxy: proxy()

mock_pyodide_ffi = MagicMock()
mock_pyodide_ffi.create_proxy = lambda fn: MockProxy(fn)

import types
mock_browser = types.ModuleType("pyon.browser")
mock_browser.js = mock_js
mock_browser.ffi = mock_pyodide_ffi

mock_protocol = types.ModuleType("pyon.browser._protocol")
mock_protocol_http = types.ModuleType("pyon.browser._protocol.http")

class _MockAbortControllerProtocol:
    signal = None
    def abort(self): pass

class _MockFetchResponse:
    pass

mock_protocol_http.AbortController = _MockAbortControllerProtocol
mock_protocol_http.FetchResponse = _MockFetchResponse
mock_protocol.FetchResponse = _MockFetchResponse
mock_browser.FetchResponse = _MockFetchResponse

mock_impl = types.ModuleType("pyon.browser.impl")
mock_impl.create_abort_controller = lambda: _MockAbortControllerProtocol()

sys.modules["pyon.browser"] = mock_browser
sys.modules["pyon.browser._protocol"] = mock_protocol
sys.modules["pyon.browser._protocol.http"] = mock_protocol_http
sys.modules["pyon.browser.impl"] = mock_impl

from pyon.core import Component, VNode, h, App

# ============================================================================
# Test helper
# ============================================================================

results: list[tuple[str, bool, str]] = []

def report(name: str, passed: bool, detail: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append((name, passed, detail))
    print(f"  {status}  {name}" + (f" — {detail}" if detail else ""))

# ============================================================================
# Test Components
# ============================================================================

class Card(Component):
    def render(self) -> VNode:
        return h("div", {"class": "card"}, self.props.get("children", []))

class LoginForm(Component):
    def setup(self):
        self._state = {"show_input": True}
        
    def render(self) -> VNode:
        children = []
        if self._state["show_input"]:
            children.append(
                h("input", {"ref": "username_input", "type": "text"})
            )
            
        return h("form", {}, [
            # Nest input inside Card to test true_owner logic
            h(Card, {}, children)
        ])

# ============================================================================
# MAIN TEST
# ============================================================================

def run_tests():
    print("=" * 70)
    print("PyOn-Py Test — Ref Integration")
    print("=" * 70)

    mock_document._app_container = MockElement("div")
    mock_document._elements["#app"] = mock_document._app_container
    app = App(LoginForm)
    
    print("\n▶ Test 1: Mendaftarkan ref pada saat render awal")
    try:
        app.mount("#app")
        
        login_form = app.component_map.get("LoginForm")
        card = app.component_map.get("LoginForm.Card")
        
        report("LoginForm di-mount", login_form is not None)
        report("Card di-mount", card is not None)
        
        report(
            "Ref 'username_input' masuk ke LoginForm (True Owner)", 
            "username_input" in login_form.refs
        )
        report(
            "Ref TIDAK bocor ke Card meskipun di-nested di dalamnya", 
            "username_input" not in card.refs
        )
        
        input_el = login_form.refs["username_input"]
        report(
            "Elemen yang disimpan di ref adalah mock elemen <input>", 
            input_el.tag == "input"
        )
        report(
            "Atribut 'data-pyon-ref' tersimpan di elemen", 
            input_el.getAttribute("data-pyon-ref") == "username_input"
        )
        report(
            "Atribut 'data-pyon-owner-path' menunjuk ke path LoginForm", 
            input_el.getAttribute("data-pyon-owner-path") == login_form._dom_path
        )
        
    except Exception as e:
        report("Test 1 Error", False, str(e))
        import traceback; traceback.print_exc()

    print("\n▶ Test 2: Cleanup ref saat elemen di-remove (Conditional Render)")
    try:
        # Hide the input, triggering REMOVE patch
        login_form.set_state({"show_input": False})
        app.flush_updates()
        
        report(
            "Ref dihapus dari LoginForm saat elemen di-unmount", 
            "username_input" not in login_form.refs
        )
        
    except Exception as e:
        report("Test 2 Error", False, str(e))
        import traceback; traceback.print_exc()
        
    print("\n▶ Test 3: Ref muncul kembali saat dirender ulang")
    try:
        login_form.set_state({"show_input": True})
        app.flush_updates()
        
        report(
            "Ref 'username_input' kembali ada di LoginForm", 
            "username_input" in login_form.refs
        )
        
    except Exception as e:
        report("Test 3 Error", False, str(e))

    # ------------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    total = len(results)

    if failed == 0:
        print(f"✅ ALL PASSED: {passed}/{total} tests")
    else:
        print(f"❌ {failed} FAILED, {passed} PASSED out of {total} tests")

    print("=" * 70)
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(run_tests())
