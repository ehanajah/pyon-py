from collections.abc import Callable
from typing import ClassVar, cast

from .component import Component
from .vnode import h


class SuspensePending(Exception):
    """Raised by lazy component when module is not resolved yet."""
    def __init__(self, lazy_class: type):
        self.lazy_class = lazy_class


class _LazyBase(Component):
    """Internal base class for lazy components."""
    _resolved: ClassVar[type | None] = None
    _loading: ClassVar[bool] = False
    _error: ClassVar[Exception | None] = None
    _loader: ClassVar[Callable]
    _subscribers: ClassVar[list[Callable[[], None]]] = []

    @classmethod
    def _start_loading(cls) -> None:
        if cls._loading:
            return
        cls._loading = True

        async def _do_load() -> None:
            try:
                resolved = await cls._loader()
                cls._resolved = resolved
                _reinject_css_if_needed()
            except Exception as e:  # noqa: BLE001
                cls._error = e
            finally:
                cls._loading = False
                # Notify all Suspense boundary subscribers
                for callback in cls._subscribers:
                    callback()
                cls._subscribers.clear()

        import asyncio
        asyncio.ensure_future(_do_load())

    def render(self):
        cls = self.__class__

        # State: resolved
        if cls._resolved is not None:
            props = dict(self.props)
            props.pop("key", None)
            children = cast(list, props.pop("children", []))
            return h(cls._resolved, props, children)

        # State: error
        if cls._error is not None:
            raise cls._error

        # State: ilde/loading
        cls._start_loading()
        raise SuspensePending(cls)


def lazy(loader: str | Callable, class_name: str | None = None):
    """
    Helper function to create a lazy component.

    Args:
        loader: The module path or a function that returns the component class.
        class_name: The name of the component class in the module.
            Required if ``loader`` is a string.
    
    Returns:
        A Component subclass that suspends import until initial render.
    """
    if isinstance(loader, str):
        module_path = loader
        if class_name is None:
            raise ValueError("class_name must be provided when loader is a string")

        async def _default_loader():
            from importlib import import_module
            module = import_module(module_path)
            return getattr(module, class_name)

        actual_loader = _default_loader
    else:
        actual_loader = loader

    display_name = class_name or "LazyComponent"

    LazyWrapper = type(display_name, (_LazyBase,), {
        "_resolved": None,
        "_loading": False,
        "_error": None,
        "_loader": staticmethod(actual_loader),
        "_subscribers": [],
    })

    return cast(type[Component], LazyWrapper)

def _reinject_css_if_needed():
    """Called after lazy component is resolved."""
    from pyon.core.css import CSSManager
    from pyon.dom.css import inject_scoped_css
    
    registry = CSSManager.get_all()
    if registry:
        inject_scoped_css(registry)
