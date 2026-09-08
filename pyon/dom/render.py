from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pyon.browser import js
from pyon.core import VNode

from .props import _apply_props

if TYPE_CHECKING:
    from pyon.core import Component, DOMElement

def _find_owner(
    node_path: str,
    component_map: "dict[str, Component]",
) -> "Component | None":
    best_path   = ""
    best_owner  = None
    for instance in component_map.values():
        dom_path = instance._dom_path
        if (node_path == dom_path or node_path.startswith(dom_path + ".")) and len(dom_path) > len(best_path):
            best_path  = dom_path
            best_owner = instance
    return best_owner

def build_path_owner_map(
    node: "VNode",
    component_map: "dict[str, Component]",
    current_path: str = "0",
) -> "dict[str, Component]":
    result: dict[str, Component] = {}
    def _walk(vnode: "VNode", path: str) -> None:
        owner = _find_owner(path, component_map)
        if owner is not None:
            result[path] = owner
        for i, child in enumerate(vnode.children):
            if isinstance(child, VNode):
                _walk(child, f"{path}.{i}")
    _walk(node, current_path)
    return result

def _build_dom_element(
    node: "VNode",
    path_owner_map: "dict[str, Component]",
    flush_callback: Callable,
    current_path: str = "0",
) -> "DOMElement":
    owner = path_owner_map.get(current_path)
    el: DOMElement = js.document.createElement(str(node.tag))
    _apply_props(el, node.props, flush_callback=flush_callback, owner=owner)
    for i, child in enumerate(node.children):
        child_path = f"{current_path}.{i}"
        if isinstance(child, VNode):
            el.appendChild(_build_dom_element(child, path_owner_map, flush_callback, child_path))
        else:
            el.appendChild(js.document.createTextNode(str(child)))
    return el

def full_render(
    tree: "VNode",
    selector: str,
    flush_callback: Callable,
    component_map: "dict[str, Component] | None" = None,
) -> None:
    container = js.document.querySelector(selector)
    if container is None:
        raise RuntimeError(f"'{selector}' selector not found in DOM")
    
    path_owner_map = (
        build_path_owner_map(tree, component_map)
        if component_map is not None
        else {}
    )
    
    container.innerHTML = ""
    container.appendChild(_build_dom_element(tree, path_owner_map, flush_callback=flush_callback))
    
    import os
    import sys
    if component_map is not None and sys.platform == "emscripten" and os.getenv("PYON_ENV") == "development":
        if not hasattr(js.window, "__pyon_py"):
            js.window.__pyon_py = type("PyonDevTools", (), {})() # type: ignore
        js.window.__pyon_py.component_map = component_map # type: ignore

        def _inspect_components() -> Any:
            import json
            def _safe(obj: Any) -> Any:
                if isinstance(obj, (int, float, str, bool, type(None))): 
                    return obj
                if isinstance(obj, dict): 
                    return {str(k): _safe(v) for k, v in obj.items() if not callable(v)}
                if isinstance(obj, list): 
                    return [_safe(i) for i in obj if not callable(i)]
                return str(obj)
            
            res = {}
            for k, v in component_map.items():
                res[k] = {
                    "type": type(v).__name__,
                    "props": _safe(v.props),
                    "state": _safe(getattr(v, "_state", {})),
                    "dom_path": getattr(v, "_dom_path", ""),
                }
            return js.JSON.parse(json.dumps(res))
        
        js.window.__pyon_py.inspect = _inspect_components # type: ignore
