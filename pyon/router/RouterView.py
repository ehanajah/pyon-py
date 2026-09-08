from __future__ import annotations

from typing import TYPE_CHECKING

from pyon.core import Component, h

from .utils import get_query_params, match_route

if TYPE_CHECKING:
    from .core import Router

class RouterView(Component):
    def setup(self):
        self._state = {
            "path": "/",
            "search": ""
        }

    @property
    def router(self) -> Router:
        router = self.inject("router")
        if router is None:
            raise RuntimeError("Router not found in context")
        return router
        
    def on_mount(self) -> None:
        self.set_state({
            "path": self.router.current_path,
            "search": self.router.current_search
        })
        self.router.subscribe(self._on_route_change)
        
    def on_unmount(self) -> None:
        self.router.unsubscribe(self._on_route_change)

    def _on_route_change(self, new_path: str) -> None:
        self.set_state({
            "path": self.router.current_path,
            "search": self.router.current_search
        })

    def render(self):
        current_path = self._state["path"]
        current_search = self._state["search"]
        
        query_params = get_query_params(current_search)
        
        fallback_route = None
        for route in self.router.routes:
            params = match_route(route["path"], current_path)
            
            if params is not None:
                combined_props = {**params, "query": query_params}
                if "key" in route:
                    combined_props["key"] = route["key"]
                
                return h(route["component"], combined_props)

            if route["path"] == "*":
                fallback_route = route

        if fallback_route:
            return h(fallback_route["component"], {"query": query_params})
        
        return h("div", {"class": "404-fallback"}, ["404 - Page Not Found"])
