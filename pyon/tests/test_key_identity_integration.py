"""
Integration test: Key-based component identity — full lifecycle simulation.

Mensimulasikan seluruh skenario interaksi user tanpa browser:
- Mock bridge layer (js module, create_proxy)
- Jalankan App, Component, _expand_tree, diff, apply_patches secara nyata
- Verifikasi state tidak bergeser saat item dihapus (key-based identity)

Run:
    python tests/test_key_identity_integration.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ============================================================================
# Mock bridge layer — simulasikan DOM tanpa browser
# ============================================================================

class MockElement:
    """Simulasi DOM element."""
    def __init__(self, tag: str = "div"):
        self.tag = tag
        self.className = ""
        self.textContent = ""
        self.attributes: dict[str, str] = {}
        self.child_nodes: list = []
        self.parent: "MockElement | None" = None
        self.style = MagicMock()
        self._event_listeners: dict[str, list] = {}

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
            if new_child in self.child_nodes:
                self.child_nodes.remove(new_child)
                idx = self.child_nodes.index(ref_child)
            self.child_nodes.insert(idx, new_child)
        else:
            self.appendChild(new_child)
        if isinstance(new_child, MockElement):
            new_child.parent = self
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

    def __repr__(self):
        return f"<{self.tag} children={len(self.child_nodes)}>"


class MockTextNode:
    """Simulasi DOM text node."""
    def __init__(self, text: str):
        self.textContent = text
        self.parent = None

    def __repr__(self):
        return f"Text({self.textContent!r})"


class MockDocument:
    """Simulasi document object."""
    def __init__(self):
        self._elements: dict[str, MockElement] = {}
        self._app_container = MockElement("div")
        self._elements["#app"] = self._app_container

    def querySelector(self, selector: str):
        return self._elements.get(selector)

    def createElement(self, tag: str):
        return MockElement(tag)

    def createTextNode(self, text: str):
        return MockTextNode(text)


class MockProxy:
    """Simulasi Pyodide create_proxy."""
    def __init__(self, fn):
        self._fn = fn
        self._destroyed = False

    def __call__(self, *args, **kwargs):
        return self._fn(*args, **kwargs)

    def destroy(self):
        self._destroyed = True


# ============================================================================
# Setup mocks
# ============================================================================

mock_document = MockDocument()

mock_js = MagicMock()
mock_js.document = mock_document
mock_js.queueMicrotask = lambda proxy: proxy()

mock_pyodide_ffi = MagicMock()
mock_pyodide_ffi.create_proxy = lambda fn: MockProxy(fn)

sys.modules["pyon.browser"] = type('MockBrowser', (), {'js': mock_js, 'ffi': mock_pyodide_ffi})()

from pyon.core import h, VNode
from pyon.core import Component
from pyon.core import App, _expand_tree
from pyon.core import diff


# ============================================================================
# Test helper
# ============================================================================

results: list[tuple[str, bool, str]] = []

def report(name: str, passed: bool, detail: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append((name, passed, detail))
    print(f"  {status}  {name}" + (f" — {detail}" if detail else ""))


# ============================================================================
# Komponen test
# ============================================================================

from typing import TypedDict

class TodoItemProps(TypedDict, total=False):
    item_id:   int
    label:     str
    on_remove: object

class TodoItemState(TypedDict):
    done: bool


class TodoItem(Component[TodoItemProps]):
    mount_log:   list[str] = []
    unmount_log: list[str] = []

    def __init__(self, props=None):
        super().__init__(props)
        self._state: TodoItemState = {"done": False}

    def on_mount(self):
        super().on_mount()
        label = (self.props or {}).get("label", "?")
        TodoItem.mount_log.append(label)

    def on_unmount(self):
        label = (self.props or {}).get("label", "?")
        TodoItem.unmount_log.append(label)
        super().on_unmount()

    def toggle(self, _event=None):
        self.set_state({"done": not self._state["done"]})

    def remove(self, _event=None):
        on_remove = (self.props or {}).get("on_remove")
        if callable(on_remove):
            item_id = (self.props or {}).get("item_id", -1)
            on_remove(item_id)

    def render(self) -> VNode:
        label = (self.props or {}).get("label", "")
        done  = self._state["done"]
        return h("li", {"class": "todo-item"}, [
            h("input", {
                "type":    "checkbox",
                "checked": done,
                "on_click": self.toggle,
            }),
            h("span", {
                "class": "todo-done" if done else "todo-label",
            }, [label]),
            h("button", {"class": "remove-btn", "on_click": self.remove}, ["✕"]),
        ])


class TodoAppState(TypedDict):
    items:     list
    next_id:   int
    input_val: str


class TodoApp(Component[dict]):
    def __init__(self, props=None):
        super().__init__(props)
        self._state: TodoAppState = {
            "items": [
                {"id": 1, "label": "Belajar PyOn-Py"},
                {"id": 2, "label": "Implementasi lifecycle hooks"},
                {"id": 3, "label": "Cek memory di DevTools"},
            ],
            "next_id":   4,
            "input_val": "",
        }

    def on_mount(self):
        super().on_mount()

    def add_item(self, _event=None):
        label = self._state["input_val"].strip()
        if not label:
            return
        new_item = {"id": self._state["next_id"], "label": label}
        self.set_state({
            "items":     self._state["items"] + [new_item],
            "next_id":   self._state["next_id"] + 1,
            "input_val": "",
        })

    def remove_item(self, item_id: int):
        self.set_state({
            "items": [i for i in self._state["items"] if i["id"] != item_id]
        })

    def render(self) -> VNode:
        items     = self._state["items"]
        input_val = self._state["input_val"]
        todo_items = [
            h(TodoItem, {
                "key":       f"todo-item-{item['id']}",
                "item_id":   item["id"],
                "label":     item["label"],
                "on_remove": self.remove_item,
            })
            for item in items
        ]
        return h("div", {"class": "todo-app"}, [
            h("h1", {}, ["PyOn-Py — Integration Test"]),
            h("div", {"class": "input-row"}, [
                h("input", {
                    "type":        "text",
                    "placeholder": "Tambah item baru...",
                    "value":       input_val,
                }),
                h("button", {"on_click": self.add_item}, ["Tambah"]),
            ]),
            h("ul", {"class": "todo-list"}, todo_items),
            h("p", {"class": "count"}, [f"{len(items)} item"]),
        ])


# ============================================================================
# MAIN TEST
# ============================================================================

def run_tests():
    print("=" * 70)
    print("PyOn-Py Integration Test — Key-Based Component Identity")
    print("=" * 70)

    errors: list[str] = []

    # ------------------------------------------------------------------
    # 1. INITIAL MOUNT
    # ------------------------------------------------------------------
    print("\n▶ Phase 1: Initial Mount")

    try:
        mock_document._app_container = MockElement("div")
        mock_document._elements["#app"] = mock_document._app_container
        TodoItem.mount_log.clear()
        TodoItem.unmount_log.clear()

        app = App(TodoApp)
        app.mount("#app")

        report(
            "component_map menggunakan key (bukan path)",
            "TodoApp" in app.component_map
            and all(not k.startswith("0.") or "todo-item" in k for k in app.component_map),
            f"keys: {list(app.component_map.keys())}"
        )

        report(
            "3 item awal + 1 root = 4 komponen di map",
            len(app.component_map) == 4,
            f"count: {len(app.component_map)}"
        )

        expected_keys = {
            "TodoApp",
            "TodoApp.todo-item-1",
            "TodoApp.todo-item-2",
            "TodoApp.todo-item-3",
        }
        report(
            "Key hierarkis benar (TodoApp.todo-item-N)",
            set(app.component_map.keys()) == expected_keys,
            f"actual: {set(app.component_map.keys())}"
        )

        report(
            "on_mount dipanggil untuk 3 TodoItem",
            len(TodoItem.mount_log) == 3,
            f"mount_log: {TodoItem.mount_log}"
        )

        root_instance = app.component_map["TodoApp"]
        report(
            "_dom_path root = '0'",
            root_instance._dom_path == "0",
            f"_dom_path: {root_instance._dom_path!r}"
        )

        def has_component_tag(node):
            if isinstance(node.tag, type):
                return True
            for child in node.children:
                if isinstance(child, VNode) and has_component_tag(child):
                    return True
            return False

        report(
            "current_tree fully expanded (no Component tags)",
            not has_component_tag(app.current_tree),
        )

    except Exception as e:
        report("Initial mount", False, f"Exception: {e}")
        errors.append(f"Phase 1: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 2. ADD ITEMS
    # ------------------------------------------------------------------
    print("\n▶ Phase 2: Tambah 3 Item Baru")

    new_labels = [
        "Item tambahan 1",
        "Item tambahan 2",
        "Item tambahan 3",
    ]

    try:
        todo_app: TodoApp = app.component_map["TodoApp"]  # type: ignore

        for label in new_labels:
            # Pakai set_state agar tidak bypass _schedule_update
            todo_app.set_state({"input_val": label})
            todo_app.add_item()

        report(
            "3 item ditambahkan → total 6 item di state",
            len(todo_app._state["items"]) == 6,
            f"count: {len(todo_app._state['items'])}"
        )

        report(
            "6 TodoItem + 1 TodoApp = 7 komponen di map",
            len(app.component_map) == 7,
            f"keys: {list(app.component_map.keys())}"
        )

        for i in range(4, 7):
            key = f"TodoApp.todo-item-{i}"
            report(
                f"Key '{key}' ada di map",
                key in app.component_map,
            )

        labels_in_state = [item["label"] for item in todo_app._state["items"]]
        for label in new_labels:
            report(
                f"Item '{label}' ada di state",
                label in labels_in_state,
            )

    except Exception as e:
        report("Add items", False, f"Exception: {e}")
        errors.append(f"Phase 2: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 3. CHECK ITEMS
    # ------------------------------------------------------------------
    print("\n▶ Phase 3: Check 3 Item (pertama, terakhir, acak)")

    try:
        item1: TodoItem = app.component_map["TodoApp.todo-item-1"]  # type: ignore
        item1.toggle()
        report("Item 1 checked → done=True", item1._state["done"] is True)

        item6: TodoItem = app.component_map["TodoApp.todo-item-6"]  # type: ignore
        item6.toggle()
        report("Item 6 checked → done=True", item6._state["done"] is True)

        item3: TodoItem = app.component_map["TodoApp.todo-item-3"]  # type: ignore
        item3.toggle()
        report("Item 3 checked → done=True", item3._state["done"] is True)

        item2: TodoItem = app.component_map["TodoApp.todo-item-2"]  # type: ignore
        report("Item 2 tetap unchecked", item2._state["done"] is False)

    except Exception as e:
        report("Check items", False, f"Exception: {e}")
        errors.append(f"Phase 3: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 4. DELETE
    # ------------------------------------------------------------------
    print("\n▶ Phase 4: Hapus 1 Unchecked (item-2) dan 1 Checked (item-3)")

    try:
        TodoItem.unmount_log.clear()

        # Simpan reference sebelum delete untuk verifikasi proxy
        item2_ref: TodoItem = app.component_map["TodoApp.todo-item-2"]  # type: ignore
        item3_ref: TodoItem = app.component_map["TodoApp.todo-item-3"]  # type: ignore
        proxies_item2 = list(item2_ref._cleanups)
        proxies_item3 = list(item3_ref._cleanups)

        todo_app.remove_item(2)
        report(
            "Item 2 dihapus dari state",
            all(i["id"] != 2 for i in todo_app._state["items"]),
            f"items: {[i['id'] for i in todo_app._state['items']]}"
        )
        report(
            "Key 'TodoApp.todo-item-2' dihapus dari map",
            "TodoApp.todo-item-2" not in app.component_map,
        )

        todo_app.remove_item(3)
        report(
            "Item 3 dihapus dari state",
            all(i["id"] != 3 for i in todo_app._state["items"]),
        )
        report(
            "Key 'TodoApp.todo-item-3' dihapus dari map",
            "TodoApp.todo-item-3" not in app.component_map,
        )

        report(
            "on_unmount dipanggil untuk 2 item yang dihapus",
            len(TodoItem.unmount_log) == 2,
            f"unmount_log: {TodoItem.unmount_log}"
        )

        report(
            "Sisa 4 item di state",
            len(todo_app._state["items"]) == 4,
            f"ids: {[i['id'] for i in todo_app._state['items']]}"
        )

        # Verifikasi proxy di-destroy setelah on_unmount
        if proxies_item2:
            report(
                "Proxy item-2 di-destroy setelah on_unmount",
                all(p.__self__._destroyed for p in proxies_item2),
                f"destroyed: {[p.__self__._destroyed for p in proxies_item2]}"
            )
            report(
                "_cleanups item-2 dikosongkan setelah on_unmount",
                len(item2_ref._cleanups) == 0,
                f"remaining: {len(item2_ref._cleanups)}"
            )
        if proxies_item3:
            report(
                "Proxy item-3 di-destroy setelah on_unmount",
                all(p.__self__._destroyed for p in proxies_item3),
                f"destroyed: {[p.__self__._destroyed for p in proxies_item3]}"
            )

    except Exception as e:
        report("Delete items", False, f"Exception: {e}")
        errors.append(f"Phase 4: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 5. KEY IDENTITY — state tidak bergeser setelah delete
    # ------------------------------------------------------------------
    print("\n▶ Phase 5: Verifikasi Key Identity (state tidak bergeser)")

    try:
        item1_after: TodoItem = app.component_map["TodoApp.todo-item-1"]  # type: ignore
        report(
            "Item 1 masih checked (done=True) setelah delete",
            item1_after._state["done"] is True,
            "Key-based identity mempertahankan state"
        )
        report(
            "Item 1 adalah instance yang SAMA (bukan baru)",
            item1_after is item1,
            "Identitas objek terjaga"
        )

        item4: TodoItem = app.component_map["TodoApp.todo-item-4"]  # type: ignore
        report(
            "Item 4 masih unchecked setelah delete item lain",
            item4._state["done"] is False,
        )

        item6_after: TodoItem = app.component_map["TodoApp.todo-item-6"]  # type: ignore
        report(
            "Item 6 masih checked (done=True) setelah delete",
            item6_after._state["done"] is True,
        )
        report(
            "Item 6 adalah instance yang SAMA",
            item6_after is item6,
        )

    except Exception as e:
        report("Key identity", False, f"Exception: {e}")
        errors.append(f"Phase 5: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 6. TOGGLE BERULANG
    # ------------------------------------------------------------------
    print("\n▶ Phase 6: Toggle Beberapa Kali")

    try:
        item1_after.toggle()
        report("Uncheck item 1 → done=False", item1_after._state["done"] is False)

        item4.toggle()
        report("Check item 4 → done=True", item4._state["done"] is True)

        item6_after.toggle()
        report("Uncheck item 6 → done=False", item6_after._state["done"] is False)

        item5: TodoItem = app.component_map["TodoApp.todo-item-5"]  # type: ignore
        item5.toggle()
        report("Check item 5 → done=True", item5._state["done"] is True)

        item1_after.toggle()
        report("Re-check item 1 → done=True", item1_after._state["done"] is True)

        item5.toggle()
        report("Uncheck item 5 → done=False", item5._state["done"] is False)

        expected_states = {
            "TodoApp.todo-item-1": True,
            "TodoApp.todo-item-4": True,
            "TodoApp.todo-item-5": False,
            "TodoApp.todo-item-6": False,
        }
        all_correct = True
        for key, expected_done in expected_states.items():
            inst: TodoItem = app.component_map[key]  # type: ignore
            if inst._state["done"] != expected_done:
                all_correct = False
                report(
                    f"State {key}",
                    False,
                    f"expected done={expected_done}, got {inst._state['done']}"
                )
        if all_correct:
            report("Semua state akhir benar setelah toggle berulang", True)

    except Exception as e:
        report("Toggle items", False, f"Exception: {e}")
        errors.append(f"Phase 6: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 7. ERROR HANDLING — key wajib
    # ------------------------------------------------------------------
    print("\n▶ Phase 7: Error Handling — Key Wajib")

    try:
        class NoKeyComponent(Component):
            def render(self):
                return h("div", {}, ["no key"])

        try:
            _expand_tree(
                h(NoKeyComponent, {"label": "test"}),
                path="0",
                parent_key="",
                component_map={},
                app=app,
            )
            report("ValueError raised jika key hilang", False, "Tidak ada exception")
        except ValueError as e:
            report(
                "ValueError raised jika key hilang",
                "must have 'key' props" in str(e),
                f"msg: {e}"
            )

    except Exception as e:
        report("Error handling", False, f"Exception: {e}")
        errors.append(f"Phase 7: {e}")

    # ------------------------------------------------------------------
    # 8. CURRENT TREE KONSISTEN
    # ------------------------------------------------------------------
    print("\n▶ Phase 8: Verifikasi current_tree Konsisten")

    try:
        tree = app.current_tree
        report("current_tree tidak None", tree is not None)

        report(
            "Root tag = 'div' (expanded)",
            tree.tag == "div",
            f"tag: {tree.tag}"
        )

        ul_node = next(
            (c for c in tree.children if isinstance(c, VNode) and c.tag == "ul"),
            None
        )
        report(
            "Menemukan <ul> dengan 4 <li> children",
            ul_node is not None and len(ul_node.children) == 4,
            f"children count: {len(ul_node.children) if ul_node else 'N/A'}"
        )

        all_paths_valid = all(
            bool(inst._dom_path)
            for inst in app.component_map.values()
        )
        report("Semua instance punya _dom_path valid", all_paths_valid)

    except Exception as e:
        report("Tree verification", False, f"Exception: {e}")
        errors.append(f"Phase 8: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 9. PROXY CLEANUP
    # ------------------------------------------------------------------
    print("\n▶ Phase 9: Proxy Cleanup Verification")

    try:
        # Simpan reference item-4 sebelum hapus
        item4_ref: TodoItem = app.component_map.get("TodoApp.todo-item-4")  # type: ignore
        proxies_before = list(item4_ref._cleanups) if item4_ref else []

        if not proxies_before:
            report(
                "Proxy terdaftar di item-4",
                False,
                "Tidak ada proxy — pastikan event handler terdaftar di render()"
            )
        else:
            todo_app.remove_item(4)

            report(
                "Proxy item-4 di-destroy setelah on_unmount",
                all(p.__self__._destroyed for p in proxies_before),
                f"destroyed: {[p.__self__._destroyed for p in proxies_before]}"
            )
            report(
                "_cleanups item-4 dikosongkan setelah on_unmount",
                len(item4_ref._cleanups) == 0,
                f"remaining: {len(item4_ref._cleanups)}"
            )
            report(
                "Key 'TodoApp.todo-item-4' dihapus dari map",
                "TodoApp.todo-item-4" not in app.component_map,
            )

    except Exception as e:
        report("Proxy cleanup", False, f"Exception: {e}")
        errors.append(f"Phase 9: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 10. COMPONENT KEY SEPARATION
    # ------------------------------------------------------------------
    print("\n▶ Phase 10: component_key Tidak Mencemari key Lokal")

    try:
        tree = app.current_tree
        ul_node = next(
            (c for c in tree.children if isinstance(c, VNode) and c.tag == "ul"),
            None
        )

        if ul_node is None or not ul_node.children:
            report("Menemukan <ul> untuk verifikasi", False, "ul tidak ditemukan")
        else:
            first_li = ul_node.children[0]

            # component_key harus berisi full hierarchical key
            report(
                "component_key berisi full hierarchical key",
                first_li.component_key is not None
                and first_li.component_key.startswith("TodoApp.todo-item-"),
                f"component_key: {first_li.component_key!r}"
            )

            # key lokal tidak boleh ditimpa full key
            report(
                "key lokal tidak berisi full hierarchical key",
                first_li.key != first_li.component_key,
                f"key: {first_li.key!r}, component_key: {first_li.component_key!r}"
            )

            # Verifikasi semua li di ul punya component_key yang unik
            comp_keys = [
                c.component_key for c in ul_node.children
                if isinstance(c, VNode)
            ]
            report(
                "Semua <li> punya component_key unik",
                len(comp_keys) == len(set(comp_keys)) and all(k for k in comp_keys),
                f"component_keys: {comp_keys}"
            )

    except Exception as e:
        report("component_key separation", False, f"Exception: {e}")
        errors.append(f"Phase 10: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    total  = len(results)

    if failed == 0:
        print(f"✅ ALL PASSED: {passed}/{total} tests")
    else:
        print(f"❌ {failed} FAILED, {passed} PASSED out of {total} tests")
        print("\nFailed tests:")
        for name, p, detail in results:
            if not p:
                print(f"  ❌ {name}: {detail}")

    if errors:
        print("\nExceptions during test:")
        for e in errors:
            print(f"  - {e}")

    print("=" * 70)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())