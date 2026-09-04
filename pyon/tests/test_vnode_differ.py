"""
VNode and diff — test suite

Run from parent folder:
    pytest tests/test_vnode_differ.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pyon.core import VNode, h
from pyon.core import diff


# =============================================================================
# VNode - construction and helper h()
# =============================================================================

class TestVNode:
    def test_vnode_default_props_dan_children(self):
        node = VNode("div")
        assert node.tag == "div"
        assert node.props == {}
        assert node.children == []
        assert node.key is None

    def test_vnode_with_props(self):
        node = VNode("button", {"class": "primary", "disabled": True})
        assert node.props["class"] == "primary"
        assert node.props["disabled"] is True

    def test_vnode_key_transfer_from_props(self):
        # key in props is automatically transferred to .key
        node = VNode("li", {"key": "item-1"}, [])
        assert node.key == "item-1"

    def test_h_helper_equivalent_with_vnode(self):
        via_class = VNode("div", {"class": "box"}, ["text"])
        via_h     = h("div", {"class": "box"}, ["text"])
        assert via_class.tag      == via_h.tag
        assert via_class.props    == via_h.props
        assert via_class.children == via_h.children

    def test_h_helper_default_empty(self):
        node = h("span")
        assert node.props == {}
        assert node.children == []

    def test_vnode_nested(self):
        tree = h("div", {}, [
            h("p", {}, ["paragraf"]),
            h("span", {}, [42]),
        ])
        assert len(tree.children) == 2
        assert tree.children[0].tag == "p" # type: ignore
        assert tree.children[1].children[0] == 42 # type: ignore


# =============================================================================
# diff — kasus dasar: CREATE, REMOVE, REPLACE
# =============================================================================

class TestDiffDasar:
    def test_create_from_none(self):
        """None → VNode must generate CREATE."""
        new = h("div")
        patches = diff(None, new)
        assert len(patches) == 1
        assert patches[0]["op"] == "CREATE"
        assert patches[0]["path"] == "0"
        assert patches[0]["node"] is new

    def test_remove_to_none(self):
        """VNode → None must generate REMOVE."""
        old = h("div")
        patches = diff(old, None)
        assert len(patches) == 1
        assert patches[0]["op"] == "REMOVE"
        assert patches[0]["path"] == "0"

    def test_both_none_no_patch(self):
        patches = diff(None, None)
        assert patches == []

    def test_replace_different_tag(self):
        """Different tag must replace the whole subtree (REPLACE)."""
        old = h("div")
        new = h("span")
        patches = diff(old, new)
        assert len(patches) == 1
        assert patches[0]["op"] == "REPLACE"
        assert patches[0]["node"] is new

    def test_replace_different_tag_but_same_props(self):
        old = h("div", {"class": "box"})
        new = h("section", {"class": "box"})
        patches = diff(old, new)
        assert patches[0]["op"] == "REPLACE"

    def test_no_patch_if_identical(self):
        node = h("div", {"class": "box"}, ["hello"])
        patches = diff(node, node)
        assert patches == []


# =============================================================================
# diff — UPDATE_PROPS
# =============================================================================

class TestDiffProps:
    def test_update_props_changed(self):
        old = h("div", {"class": "a"})
        new = h("div", {"class": "b"})
        patches = diff(old, new)
        assert len(patches) == 1
        p = patches[0]
        assert p["op"] == "UPDATE_PROPS"
        assert p["props"]["class"] == "b"

    def test_update_props_added(self):
        old = h("input", {})
        new = h("input", {"placeholder": "type here..."})
        patches = diff(old, new)
        assert any(p["op"] == "UPDATE_PROPS" for p in patches)
        prop_patch = next(p for p in patches if p["op"] == "UPDATE_PROPS")
        assert prop_patch["props"]["placeholder"] == "type here..."

    def test_update_props_removed(self):
        """Missing prop in new is None in patch."""
        old = h("div", {"class": "old", "id": "x"})
        new = h("div", {"class": "old"})       # "id" missing
        patches = diff(old, new)
        prop_patch = next((p for p in patches if p["op"] == "UPDATE_PROPS"), None)
        assert prop_patch is not None
        assert prop_patch["props"].get("id") is None

    def test_update_props_no_change_if_same(self):
        old = h("div", {"class": "sama"})
        new = h("div", {"class": "sama"})
        patches = diff(old, new)
        assert not any(p["op"] == "UPDATE_PROPS" for p in patches)

    def test_event_handler_ignored_from_props_diff(self):
        """Callable (event handler) cannot be included in UPDATE_PROPS patch."""
        handler = lambda e: None  # noqa: E731
        old = h("button", {"onClick": handler})
        new = h("button", {"onClick": lambda e: None})  # instance different
        patches = diff(old, new)
        prop_patch = next((p for p in patches if p["op"] == "UPDATE_PROPS"), None)
        # May not have patch, or contain "onClick" but not the handler
        if prop_patch:
            assert "onClick" not in prop_patch["props"]


# =============================================================================
# diff — SET_TEXT
# =============================================================================

class TestDiffText:
    def test_set_text_changed(self):
        old = h("p", {}, ["teks lama"])
        new = h("p", {}, ["teks baru"])
        patches = diff(old, new)
        assert len(patches) == 1
        p = patches[0]
        assert p["op"] == "SET_TEXT"
        assert p["text"] == "teks baru"

    def test_set_text_number_to_number(self):
        old = h("span", {}, [0])
        new = h("span", {}, [5])
        patches = diff(old, new)
        assert patches[0]["op"] == "SET_TEXT"
        assert patches[0]["text"] == "5"

    def test_no_patch_if_same_text(self):
        old = h("p", {}, ["sama"])
        new = h("p", {}, ["sama"])
        patches = diff(old, new)
        assert patches == []


# =============================================================================
# diff — children (path tracking)
# =============================================================================

class TestDiffChildren:
    def test_create_new_child(self):
        """Parent same, new child added → REORDER_CHILDREN at parent."""
        old = h("ul", {}, [])
        new = h("ul", {}, [h("li", {}, ["item"])])
        patches = diff(old, new)
        assert any(p["op"] == "REORDER_CHILDREN" and p["path"] == "0" for p in patches)

    def test_remove_child(self):
        """Child removed → REORDER_CHILDREN at parent."""
        old = h("ul", {}, [h("li", {}, ["item"])])
        new = h("ul", {}, [])
        patches = diff(old, new)
        assert any(p["op"] == "REORDER_CHILDREN" and p["path"] == "0" for p in patches)

    def test_replace_child_tag(self):
        old = h("div", {}, [h("span", {})])
        new = h("div", {}, [h("p", {})])
        patches = diff(old, new)
        assert patches[0]["op"] == "REORDER_CHILDREN"
        assert patches[0]["path"] == "0"

    def test_path_second_child(self):
        """Second child uses path '0.1'."""
        old = h("div", {}, [h("span"), h("span")])
        new = h("div", {}, [h("span"), h("p")])   # anak kedua berubah
        patches = diff(old, new)
        reorder = next(p for p in patches if p["op"] == "REORDER_CHILDREN")
        assert reorder["path"] == "0"

    def test_path_nested_three_levels(self):
        old = h("div", {}, [
            h("section", {}, [
                h("p", {}, ["lama"])
            ])
        ])
        new = h("div", {}, [
            h("section", {}, [
                h("p", {}, ["baru"])
            ])
        ])
        patches = diff(old, new)
        assert any(p["op"] == "SET_TEXT" and p["path"] == "0.0.0" for p in patches)

    def test_several_changes_at_once(self):
        """Props changed at parent + text changed at child."""
        old = h("div", {"class": "a"}, [h("p", {}, ["lama"])])
        new = h("div", {"class": "b"}, [h("p", {}, ["baru"])])
        patches = diff(old, new)
        ops = [p["op"] for p in patches]
        assert "UPDATE_PROPS" in ops
        assert "SET_TEXT" in ops


# =============================================================================
# diff — tree component class (not string tag)
# =============================================================================

class FakeComponent:
    """Custom component placeholder."""
    pass

class OtherComponent:
    pass

class TestDiffKomponenClass:
    def test_replace_if_different_class(self):
        old = h(FakeComponent)
        new = h(OtherComponent)
        patches = diff(old, new)
        assert patches[0]["op"] == "REPLACE"

    def test_no_replace_if_same_class(self):
        old = h(FakeComponent, {"val": 1})
        new = h(FakeComponent, {"val": 2})
        patches = diff(old, new)
        # Tidak ada REPLACE, tapi ada UPDATE_PROPS
        assert not any(p["op"] == "REPLACE" for p in patches)
        assert any(p["op"] == "UPDATE_PROPS" for p in patches)