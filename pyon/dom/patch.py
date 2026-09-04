from typing import TYPE_CHECKING, Callable, cast, Union
from pyon.browser import js

from .props import _apply_props, _BOOLEAN_ATTRS
from .render import _build_dom_element, build_path_owner_map, _find_owner

if TYPE_CHECKING:
    from pyon.core import Patch, CreatePatch, ReplacePatch, UpdatePropsPatch, SetTextPatch, ReorderChildrenPatch
    from pyon.core import Component
    from pyon.core import DOMElement


def _get_element_by_path(path: str, root_selector: str) -> "DOMElement":
    container = js.document.querySelector(root_selector)
    if container is None:
        raise RuntimeError(f"Cannot find root element with selector {root_selector}")
    el = container.children[0]
    parts = path.split(".")
    for part in parts[1:]:
        el = el.childNodes[int(part)]
    return el # type: ignore


def _apply_single_patch(
    patch: "Patch",
    root_selector: str,
    path_owner_map: "dict[str, Component]",
    flush_callback: Callable,
) -> None:
    op   = patch["op"]
    path = patch["path"]

    if op == "CREATE":
        c_patch = cast("CreatePatch", patch)
        parts = path.split(".")
        parent_path = ".".join(parts[:-1])
        new_el = _build_dom_element(
            c_patch["node"],
            path_owner_map,
            flush_callback,
            path,
        )
        parent = _get_element_by_path(parent_path, root_selector)
        parent.appendChild(new_el)

    elif op == "REMOVE":
        _get_element_by_path(path, root_selector).remove()

    elif op == "REPLACE":
        r_patch = cast("ReplacePatch", patch)
        el = _get_element_by_path(path, root_selector)
        new_el = _build_dom_element(
            r_patch["node"],
            path_owner_map,
            flush_callback,
            current_path=path,
        )
        el.replaceWith(new_el)

    elif op == "UPDATE_PROPS":
        u_patch = cast("UpdatePropsPatch", patch)
        el = _get_element_by_path(path, root_selector)
        props = u_patch["props"]
        owner = path_owner_map.get(path)
        for key, val in props.items():
            if val is None:
                if key in _BOOLEAN_ATTRS:
                    setattr(el, key, False)
                el.removeAttribute(key)
            else:
                _apply_props(el, {key: val}, flush_callback, owner=owner)

    elif op == "REORDER_CHILDREN":
        re_patch = cast("ReorderChildrenPatch", patch)
        parent = _get_element_by_path(path, root_selector)
        old_nodes = list(parent.childNodes)
        mapping = re_patch["mapping"]

        for new_idx, item in enumerate(mapping):
            if isinstance(item, int):
                el = old_nodes[item]
            else:
                child_path = f"{path}.{new_idx}"
                if isinstance(item, (str, int, float)):
                    el = js.document.createTextNode(str(item))
                else:
                    el = _build_dom_element(item, path_owner_map, flush_callback, current_path=child_path)

            if new_idx < len(parent.childNodes):
                if parent.childNodes[new_idx] is not el:
                    parent.insertBefore(el, parent.childNodes[new_idx])
            else:
                parent.appendChild(el)

        mapped_old_indices = {item for item in mapping if isinstance(item, int)}
        for i, old_node in enumerate(old_nodes):
            if i not in mapped_old_indices:
                old_node.remove()

    elif op == "SET_TEXT":
        st_patch = cast("SetTextPatch", patch)
        el = _get_element_by_path(path, root_selector)
        el.textContent = st_patch["text"]


def apply_patches(
    patches: "list[Patch]",
    root_selector: str,
    flush_callback: Callable,
    component_map: "dict[str, Component] | None" = None,
) -> None:
    _cmap = component_map or {}

    for patch in patches:
        if patch["op"] in ("CREATE", "REPLACE"):
            node = cast("Union[CreatePatch, ReplacePatch]", patch).get("node")
            path_owner_map = build_path_owner_map(node, _cmap, patch["path"]) if node else {}

        elif patch["op"] == "REORDER_CHILDREN":
            path_owner_map = {}
            if _cmap:
                owner = _find_owner(patch["path"], _cmap)
                if owner is not None:
                    path_owner_map[patch["path"]] = owner
                for i, item in enumerate(cast("ReorderChildrenPatch", patch).get("mapping", [])):
                    if not isinstance(item, (int, str, float)):
                        child_path = f"{patch['path']}.{i}"
                        path_owner_map.update(build_path_owner_map(item, _cmap, child_path))

        else:
            path_owner_map = {}
            if _cmap:
                owner = _find_owner(patch["path"], _cmap)
                if owner is not None:
                    path_owner_map[patch["path"]] = owner

        _apply_single_patch(patch, root_selector, path_owner_map, flush_callback)
