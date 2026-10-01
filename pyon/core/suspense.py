from typing import ClassVar

from .component import BaseEvents, BaseProps, BaseState, Component
from .lazy import _LazyBase
from .vnode import VNode, h


class SuspenseCaughtByBoundary(Exception):
    """Internal exception for the Suspense Caught By Boundary mechanism (stack unwinding)."""
    def __init__(self, boundary_key: str, lazy_class: type[_LazyBase]):
        self.boundary_key = boundary_key
        self.lazy_class = lazy_class


class SuspenseProps(BaseProps):
    fallback: VNode | str


class Suspense(Component[SuspenseProps, BaseState, BaseEvents]):
    """
    Boundary component that catches SuspensePending exceptions from 
    _LazyBase components subclasses and render fallback UI while loading.

    Props:
        fallback: VNode | str - Fallback UI to render while loading.
                    Default: <div></div> (empty div).
        children: main content (lazy component).
    """

    _is_suspense_boundary: ClassVar[bool] = True

    def setup(self):
        self._state = {"pending": False}
        self._pending_lazies: set[type[_LazyBase]] = set()

    def _register_pending(self, lazy_class: type[_LazyBase]) -> None:
        """Called by _expand_tree when SuspenseComponent is encountered."""
        if lazy_class not in self._pending_lazies:
            self._pending_lazies.add(lazy_class)
            lazy_class._subscribers.append(self._on_resolved)

    def _on_resolved(self):
        """Callback when when one of the pending lazy components is resolved."""
        self._pending_lazies = {
            lc for lc in self._pending_lazies
            if lc._resolved is not None and lc._error is None
        }
        # Treiggers re-render
        self.set_state({"pending" : len(self._pending_lazies) > 0})

    def _get_fallback_vnode(self):
        """Returns fallback UI based on props.fallback."""
        fallback = self.props.get("fallback")
        if fallback is None:
            return h("div", {}, [])
        if isinstance(fallback, str):
            from .template import parse, render_element, tokenize
            token = tokenize(fallback)
            ast = parse(token)
            return render_element(ast, self, {})
        if isinstance(fallback, type):
            return h(fallback, {}, [])
        if isinstance(fallback, VNode):
            return fallback
        raise TypeError(f"Invalid fallback type: {type(fallback)}")

    def render(self):
        children = self.props.get("children", [])
        return h("pyon-fragment", {}, children)
    