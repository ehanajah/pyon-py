from typing import Callable, TypedDict, Any

from pyon.browser import js, ffi

from .utils import get_query_params

class RouteDef(TypedDict):
    path: str
    component: type
    key: str

class Router:
    def __init__(self, routes: list[RouteDef]) -> None:
        self.routes = routes
        self.current_path = js.window.location.pathname
        self.current_search = js.window.location.search
        self._subscribers: list[Callable[[str], None]] = []
        self._proxy = ffi.create_proxy(self._on_popstate)
        js.window.addEventListener("popstate", self._proxy)

    @property
    def query(self) -> dict[str, str]:
        return get_query_params(self.current_search)

    def _on_popstate(self, event: Any) -> None:
        self.current_path = js.window.location.pathname
        self.current_search = js.window.location.search
        self._notify()

    def push(self, full_path: str) -> None:
        path = full_path
        search = ""
        if "?" in full_path:
            path, search = full_path.split("?", 1)
            search = "?" + search

        if self.current_path == path and self.current_search == search:
            return

        js.window.history.pushState(None, "", full_path)
        js.window.scrollTo(0, 0)
        self.current_path = path
        self.current_search = search
        self._notify()

    def replace(self, full_path: str) -> None:
        path = full_path
        search = ""
        if "?" in full_path:
            path, search = full_path.split("?", 1)
            search = "?" + search

        if self.current_path == path and self.current_search == search:
            return

        js.window.history.replaceState(None, "", full_path)
        js.window.scrollTo(0, 0)
        self.current_path = path
        self.current_search = search
        self._notify()

    def _notify(self) -> None:
        for callback in self._subscribers:
            callback(self.current_path)
            
    def subscribe(self, callback: Callable[[str], None]) -> None:
        self._subscribers.append(callback)
        
    def unsubscribe(self, callback: Callable[[str], None]) -> None:
        self._subscribers.remove(callback)
        
    def destroy(self) -> None:
        """Proxy cleanup to prevent memory leak."""
        js.window.removeEventListener("popstate", self._proxy)
        self._proxy.destroy()

    def is_active(self, path: str) -> bool:
        """Check if a path is active in the router."""
        return self.current_path == path
        