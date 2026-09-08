from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pyon.browser import ffi
from pyon.core import dispatch

if TYPE_CHECKING:
    from pyon.core import Component, DOMElement, Props

_BOOLEAN_ATTRS = {
    "disabled", "checked", "readonly", "required",
    "multiple", "autofocus", "autoplay", "controls",
    "hidden", "loop", "novalidate", "open", "selected",
}

def _apply_props(
        el: "DOMElement", 
        props: "Props", 
        flush_callback: Callable,
        owner: "Component | None" = None
    ) -> None:
    for key, val in props.items():
        if key == "key":
            continue
        elif key == "class":
            el.className = str(val) if val else ""
        elif key == "style" and isinstance(val, dict):
            for prop, css_val in val.items():
                setattr(el.style, prop, css_val)
        elif key in _BOOLEAN_ATTRS:
            setattr(el, key, bool(val))
            if val:
                el.setAttribute(key, "")
            else:
                el.removeAttribute(key)
        elif key == "value":
            el.value = str(val)
            el.setAttribute(key, str(val))
        elif key.startswith("on_") and callable(val):
            event_name = key[3:]
            if owner is not None:
                def make_handler(handler: Callable) -> Callable:
                    def exec_handler(*args: Any, **kwargs: Any) -> None:
                        instance = getattr(handler, "__self__", owner)
                        dispatch(handler(*args, **kwargs), instance)
                        flush_callback()
                    return exec_handler
                
                proxy = ffi.create_proxy(make_handler(val))
                owner._cleanups.append(proxy.destroy) # type: ignore
                el.addEventListener(event_name, proxy)
            else:
                proxy = ffi.create_proxy(val)
                el.addEventListener(event_name, proxy)
        else:
            el.setAttribute(key, str(val))
