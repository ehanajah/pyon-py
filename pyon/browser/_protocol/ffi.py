from typing import Protocol, Any, Callable

class FFIProxy(Protocol):
    """Protocol for FFI Proxy object that wraps Python callable.
    Used as an event listener callback on the JavaScript side.
    """
    def destroy(self) -> None:
        """Destroy the proxy, preventing memory leaks."""
        ...


class FFI(Protocol):
    """Protocol for FFI interop Python <-> JS.
    In Pyodide, this is implemented by the `pyodide.ffi` module.
    """
    
    def create_proxy(self, obj: Callable[..., Any]) -> FFIProxy:
        """Wrap a Python callable into a JavaScript proxy to be used
        as an event listener callback on the JavaScript side or a queueMicrotask.
        """
        ...
        
    def to_js(self, obj: Any, dict_converter: Any = ...) -> Any:
        """Translate Python primitive/collection type into native JS object/array.
        (Currently not used in UI, but important for API HTTP in the future).
        """
        ...
