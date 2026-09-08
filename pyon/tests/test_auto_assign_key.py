"""
Test: Auto-assign key — class name sebagai default key untuk Component VNode.

Menguji behavior baru:
- Component tanpa key eksplisit otomatis mendapat class name sebagai key.
- Duplikasi key (baik default maupun eksplisit) di level yang sama memicu ValueError.
- Component berbeda tanpa key di level yang sama tetap valid (key default unik).

Run:
    python pyon/tests/test_auto_assign_key.py
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

# Mock AbortController protocol
class MockAbortController:
    signal = None
    def abort(self):
        pass

# Mock the full pyon.browser module hierarchy
import types

mock_browser = types.ModuleType("pyon.browser")
mock_browser.js = mock_js
mock_browser.ffi = mock_pyodide_ffi

mock_protocol = types.ModuleType("pyon.browser._protocol")
mock_protocol_http = types.ModuleType("pyon.browser._protocol.http")
mock_protocol_http.AbortController = MockAbortController

mock_impl = types.ModuleType("pyon.browser.impl")
mock_impl.create_abort_controller = lambda: MockAbortController()

sys.modules["pyon.browser"] = mock_browser
sys.modules["pyon.browser._protocol"] = mock_protocol
sys.modules["pyon.browser._protocol.http"] = mock_protocol_http
sys.modules["pyon.browser.impl"] = mock_impl

from pyon.core import h, VNode, Component, App, _expand_tree

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

class Header(Component):
    def render(self) -> VNode:
        return h("header", {}, ["Header"])


class Footer(Component):
    def render(self) -> VNode:
        return h("footer", {}, ["Footer"])


class Sidebar(Component):
    def render(self) -> VNode:
        return h("aside", {}, ["Sidebar"])


class Card(Component):
    def render(self) -> VNode:
        label = self.props.get("label", "card")
        return h("div", {"class": "card"}, [label])


class RootApp(Component):
    def render(self) -> VNode:
        return h("div", {}, ["root"])


# ============================================================================
# MAIN TEST
# ============================================================================

def run_tests():
    print("=" * 70)
    print("PyOn-Py Test — Auto-Assign Key & Duplicate Key Validation")
    print("=" * 70)

    mock_document._app_container = MockElement("div")
    mock_document._elements["#app"] = mock_document._app_container
    app = App(RootApp)
    app.mount("#app")

    # ------------------------------------------------------------------
    # 1. SINGLE COMPONENT TANPA KEY → AUTO-ASSIGN CLASS NAME
    # ------------------------------------------------------------------
    print("\n▶ Test 1: Single component tanpa key eksplisit")

    try:
        cmap: dict = {}
        tree = _expand_tree(
            h("div", {}, [
                h(Header, {}),
            ]),
            path="0", parent_key="", component_map=cmap, app=app,
        )
        report(
            "Header tanpa key → auto-assign 'Header'",
            "Header" in cmap,
            f"keys: {list(cmap.keys())}",
        )
    except Exception as e:
        report("Single component tanpa key", False, f"Exception: {e}")

    # ------------------------------------------------------------------
    # 2. DUA COMPONENT BERBEDA TANPA KEY → KEDUANYA AUTO-ASSIGN UNIK
    # ------------------------------------------------------------------
    print("\n▶ Test 2: Dua component class berbeda tanpa key")

    try:
        cmap = {}
        tree = _expand_tree(
            h("div", {}, [
                h(Header, {}),
                h(Footer, {}),
            ]),
            path="0", parent_key="", component_map=cmap, app=app,
        )
        report(
            "Header + Footer → key 'Header' dan 'Footer'",
            "Header" in cmap and "Footer" in cmap,
            f"keys: {list(cmap.keys())}",
        )
    except Exception as e:
        report("Dua component berbeda tanpa key", False, f"Exception: {e}")

    # ------------------------------------------------------------------
    # 3. TIGA COMPONENT BERBEDA TANPA KEY → SEMUA VALID
    # ------------------------------------------------------------------
    print("\n▶ Test 3: Tiga component class berbeda tanpa key")

    try:
        cmap = {}
        tree = _expand_tree(
            h("div", {}, [
                h(Header, {}),
                h(Sidebar, {}),
                h(Footer, {}),
            ]),
            path="0", parent_key="", component_map=cmap, app=app,
        )
        report(
            "Header + Sidebar + Footer → 3 key unik",
            len(cmap) == 3 and "Header" in cmap and "Sidebar" in cmap and "Footer" in cmap,
            f"keys: {list(cmap.keys())}",
        )
    except Exception as e:
        report("Tiga component berbeda tanpa key", False, f"Exception: {e}")

    # ------------------------------------------------------------------
    # 4. DUPLIKAT CLASS TANPA KEY → HARUS ValueError
    # ------------------------------------------------------------------
    print("\n▶ Test 4: Duplikat class yang sama tanpa key eksplisit")

    try:
        _expand_tree(
            h("div", {}, [
                h(Card, {}),
                h(Card, {}),
            ]),
            path="0", parent_key="", component_map={}, app=app,
        )
        report(
            "Dua Card tanpa key → ValueError",
            False,
            "Tidak ada exception, seharusnya raise ValueError",
        )
    except ValueError as e:
        report(
            "Dua Card tanpa key → ValueError (duplikat default key 'Card')",
            "Duplicate keys" in str(e),
            f"msg: {e}",
        )
    except Exception as e:
        report("Duplikat class tanpa key", False, f"Unexpected exception: {e}")

    # ------------------------------------------------------------------
    # 5. TIGA DUPLIKAT CLASS TANPA KEY → HARUS ValueError
    # ------------------------------------------------------------------
    print("\n▶ Test 5: Tiga duplikat class yang sama tanpa key")

    try:
        _expand_tree(
            h("div", {}, [
                h(Card, {}),
                h(Card, {}),
                h(Card, {}),
            ]),
            path="0", parent_key="", component_map={}, app=app,
        )
        report(
            "Tiga Card tanpa key → ValueError",
            False,
            "Tidak ada exception",
        )
    except ValueError as e:
        report(
            "Tiga Card tanpa key → ValueError",
            "Duplicate keys" in str(e),
            f"msg: {e}",
        )
    except Exception as e:
        report("Tiga duplikat class tanpa key", False, f"Unexpected: {e}")

    # ------------------------------------------------------------------
    # 6. DUPLIKAT KEY EKSPLISIT → HARUS ValueError
    # ------------------------------------------------------------------
    print("\n▶ Test 6: Key eksplisit duplikat di level yang sama")

    try:
        _expand_tree(
            h("div", {}, [
                h(Header, {"key": "same-key"}),
                h(Footer, {"key": "same-key"}),
            ]),
            path="0", parent_key="", component_map={}, app=app,
        )
        report(
            "Dua component dengan key='same-key' → ValueError",
            False,
            "Tidak ada exception",
        )
    except ValueError as e:
        report(
            "Dua component dengan key='same-key' → ValueError",
            "Duplicate keys" in str(e),
            f"msg: {e}",
        )
    except Exception as e:
        report("Key eksplisit duplikat", False, f"Unexpected: {e}")

    # ------------------------------------------------------------------
    # 7. CAMPURAN: SATU DEFAULT + SATU EKSPLISIT YANG SAMA → ValueError
    # ------------------------------------------------------------------
    print("\n▶ Test 7: Default key bertabrakan dengan key eksplisit")

    try:
        # Header tanpa key → default "Header"
        # Footer dengan key="Header" → eksplisit "Header" (tabrakan!)
        _expand_tree(
            h("div", {}, [
                h(Header, {}),
                h(Footer, {"key": "Header"}),
            ]),
            path="0", parent_key="", component_map={}, app=app,
        )
        report(
            "Default 'Header' + eksplisit 'Header' → ValueError",
            False,
            "Tidak ada exception",
        )
    except ValueError as e:
        report(
            "Default 'Header' + eksplisit 'Header' → ValueError",
            "Duplicate keys" in str(e),
            f"msg: {e}",
        )
    except Exception as e:
        report("Campuran default + eksplisit tabrakan", False, f"Unexpected: {e}")

    # ------------------------------------------------------------------
    # 8. DUPLIKAT DI LEVEL BERBEDA → TIDAK ERROR (scope per-level)
    # ------------------------------------------------------------------
    print("\n▶ Test 8: Duplikat class di level berbeda (bukan siblings)")

    try:
        class Wrapper(Component):
            def render(self) -> VNode:
                return h("div", {}, [
                    h(Card, {"key": "inner-card", "label": "inner"}),
                ])

        cmap = {}
        tree = _expand_tree(
            h("div", {}, [
                h(Card, {"key": "outer-card", "label": "outer"}),
                h(Wrapper, {}),
            ]),
            path="0", parent_key="", component_map=cmap, app=app,
        )
        report(
            "Card di level berbeda → OK (bukan siblings)",
            "outer-card" in cmap and "Wrapper.inner-card" in cmap,
            f"keys: {list(cmap.keys())}",
        )
    except Exception as e:
        report("Duplikat di level berbeda", False, f"Exception: {e}")

    # ------------------------------------------------------------------
    # 9. COMPONENT DENGAN KEY EKSPLISIT → TETAP BENAR
    # ------------------------------------------------------------------
    print("\n▶ Test 9: Component dengan key eksplisit tetap menggunakan key tersebut")

    try:
        cmap = {}
        tree = _expand_tree(
            h("div", {}, [
                h(Card, {"key": "my-card", "label": "test"}),
            ]),
            path="0", parent_key="", component_map=cmap, app=app,
        )
        report(
            "Card dengan key='my-card' → key tetap 'my-card'",
            "my-card" in cmap and "Card" not in cmap,
            f"keys: {list(cmap.keys())}",
        )
    except Exception as e:
        report("Component dengan key eksplisit", False, f"Exception: {e}")

    # ------------------------------------------------------------------
    # 10. HTML TAG TIDAK TERPENGARUH (hanya Component yang auto-assign)
    # ------------------------------------------------------------------
    print("\n▶ Test 10: HTML tag biasa tanpa key tetap OK")

    try:
        cmap = {}
        tree = _expand_tree(
            h("div", {}, [
                h("span", {}, ["A"]),
                h("span", {}, ["B"]),
                h("span", {}, ["C"]),
            ]),
            path="0", parent_key="", component_map=cmap, app=app,
        )
        report(
            "Tiga <span> tanpa key → OK (HTML tag bukan Component)",
            True,
        )
    except Exception as e:
        report("HTML tag biasa", False, f"Exception: {e}")

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
        print("\nFailed tests:")
        for name, p, detail in results:
            if not p:
                print(f"  ❌ {name}: {detail}")

    print("=" * 70)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
