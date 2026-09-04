from __future__ import annotations
from typing import TYPE_CHECKING

from pyon.core import Component, BaseProps, h
from pyon.core.events import Event

if TYPE_CHECKING:
    from .core import Router

class LinkProps(BaseProps):
    to: str

class Link(Component[LinkProps]):
    def setup(self):
        self._state = {"is_active": False}

    @property
    def router(self) -> Router:
        router = self.inject("router")
        if router is None:
            raise RuntimeError("Router not found in context")
        return router

    def _on_route_change(self, path: str) -> None:
        is_now_active = self.router.is_active(self.props["to"])
        self.set_state({"is_active": is_now_active})

    def on_mount(self) -> None:
        self.set_state({"is_active": self.router.is_active(self.props["to"])})
        self.router.subscribe(self._on_route_change)

    def on_unmount(self) -> None:
        self.router.unsubscribe(self._on_route_change)
    
    def _handle_click(self, event: Event) -> None:
        event.preventDefault()
        self.router.push(self.props["to"])
        
    def render(self):
        classes = "router-link"
        if self._state["is_active"]:
            classes +=" active"
            
        attrs = {k: v for k, v in self.props.items() if k not in ["to", "children", "key"]}
        
        return h("a", {
            "href": self.props["to"],
            "class": classes,
            "on_click": self._handle_click,
            **attrs
        }, self.props.get("children", []))
