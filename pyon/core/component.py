"""Component Module — the base class for all UI components in Pyon-Py.

This module provides the ``Component`` class which must be subclassed by
users to create UI components. The design pattern follows React
class components: props enter from the outside, state is managed internally,
and ``render()`` returns a VNode tree.

Usage example::

    class Counter(Component["CounterProps", "CounterState"]):
        def __init__(self, props):
            super().__init__(props)
            self._state = {"count": 0}

        def increment(self):
            self.set_state({"count": self._state["count"] + 1})

        def render(self) -> VNode:
            return h("button", {"on_click": self.increment}, [
                f"Click: {self._state['count']}"
            ])
"""

from __future__ import annotations
from collections import deque
from typing import Any, Mapping, Optional, TYPE_CHECKING, cast, Callable, TypedDict, final
from typing_extensions import Generic, TypeVar

if TYPE_CHECKING:
    # Import VNode only during type-checking to avoid circular imports.
    # At runtime, this type is not needed because render() returns a
    # VNode object that has already been imported by the caller (core/app.py).
    from .vnode import VNode


class BaseProps(TypedDict, total=False):
    """Base definition for component properties with type support.

    This class provides common keys applicable to all components.
    Subclass ``BaseProps`` to define component-specific props
    with type safety.

    Attributes:
        key: Unique key for keyed reconciliation in ``core/differ.py``.
            Used to identify components in dynamic lists.
        children: List of child elements passed to the component.

    Example:
        Defining props for a custom component::

            class TodoItemProps(BaseProps):
                text: str
                completed: bool
                on_remove: Callable[[int], None]
    """

    key: str
    children: list[Any]


# TypeVar for generic Props — must be a Mapping (dict-like).
# Allows Component subclasses to declare their props type explicitly.
PropsT = TypeVar("PropsT", bound=Mapping[str, Any], default=BaseProps)

EventsT = TypeVar("EventsT", bound=Mapping[str, Callable])


class Component(Generic[PropsT]):
    """Base class for all user-defined UI components.

    Component follows the React class component pattern:
    - ``props`` is received from the parent component (immutable by convention).
    - ``_state`` is managed internally and updated via ``set_state()``.
    - ``render()`` returns a VNode tree describing the UI.

    Component Lifecycle:
    1. ``__init__(props)`` — initialization, sets the initial state.
    2. ``render()`` — called by ``_expand_tree()`` in ``core/app.py``
       to obtain the VNode tree.
    3. ``on_mount()`` — called once after the component is first
       created (in ``_expand_tree()``).
    4. ``set_state(updates)`` — triggers a re-render via ``_schedule_update``.
    5. ``on_unmount()`` — called when the component is removed (orphan detection
       in ``App._update_from_key()``).

    Attributes:
        props: Properties received from the parent component. Its type
            is determined by the generic ``PropsT``.
        _state: Internal state of the component. Initialized by the subclass
            in ``__init__`` and updated via ``set_state()``.
        _dirty: Batching flag to prevent rescheduling updates
            if an update is already scheduled. Set to ``True`` when
            ``set_state()`` is called, reset to ``False`` after
            ``_schedule_update()`` completes.
        _cleanups: List of generic cleanup closures (e.g., JS Proxy destroy
            methods) created when ``_apply_props()`` in the bridge binds Python
            event handlers. Stored here to prevent them from being GC'ed by
            the browser or runtime. Executed and cleared in ``on_unmount()``.
        _dom_path: Current DOM path (e.g., ``"body>div:0>ul:0>li:2"``).
            Set by ``_expand_tree()`` in ``core/app.py`` and used
            by ``build_path_owner_map()`` in ``pyodide_impl.py`` to
            determine which component owns a specific DOM node.
        _schedule_update: Callback to schedule a re-render.
            Bound to ``App._update_from_key(key)`` by ``_expand_tree()``
            in ``core/app.py`` using ``functools.partial``.

    Example:
        Creating a simple component::

            class Greeting(Component):
                def __init__(self, props):
                    super().__init__(props)
                    self._state = {"name": "World"}

                def render(self) -> VNode:
                    return h("p", {}, [f"Hello, {self._state['name']}!"])
    """

    props: PropsT
    _state: dict[str, Any]
    _prev_props: PropsT
    _prev_state: dict[str, Any]
    _dirty: bool  # batching flag: prevents rescheduling updates if an update is already scheduled
    _updates: deque[Callable[[], None]]  # stores pending update callbacks (e.g., set_state closures)
    _cleanups: list[Callable[[], None]]  # stores generic cleanup callbacks (e.g. proxy.destroy)
    _dom_path: str  # current DOM path — set by _expand_tree, used by build_path_owner_map
    _mounted = False
    _schedule_update: Callable[[], None]
    _enqueue_dirty: Callable[[], None]
    _provided: dict[str, Any]  # stores provided context values for this component
    _contexts: dict[str, Any]  # stores context providers for this component

    @property
    def events(self) -> dict[str, Callable]:
        return {}

    @final
    def __init__(self, props: Optional[PropsT] = None) -> None:
        """Initializes the component's internal attributes.
 
        This method is called automatically by the framework during component
        instantiation. **Do not override this method** in subclasses — use
        :meth:`setup` instead for state initialization and context access.
 
        If you must override ``__init__`` (e.g., to modify props before
        they are stored), always call ``super().__init__(props)`` first and
        avoid accessing :meth:`inject` here, as the context has not yet been
        copied from the parent at this point.
 
        Args:
            props: Dictionary of properties passed down from the parent
                component. Defaults to ``None`` (stored as an empty dict).
                Example: ``{"label": "Click me", "on_click": handler}``.
 
        See Also:
            :meth:`setup` — the recommended place for state initialization
            and context-dependent logic.
        """
        self.props = props if props is not None else cast(PropsT, {})
        self._state = {}  # populated by subclasses in their respective __init__
        self._prev_props = cast(PropsT, {})
        self._prev_state = {}
        self._dirty = False
        self._updates = deque()
        self._cleanups = []
        self._dom_path = ""
        self._mounted = False  # flag to track if on_mount has been called
        # No-op placeholder; will be overwritten by _expand_tree() in core/app.py
        # with functools.partial(app._update_from_key, component_key, prev_props, prev_state).
        self._schedule_update = lambda : None
        self._enqueue_dirty = lambda : None

        # Initialize context providers
        self._provided = {}
        self._contexts = {}

    def setup(self) -> None:
        """Lifecycle hook called once after the component is instantiated and
        its context has been populated.
 
        This is the recommended place to initialize ``self._state``, declare
        instance attributes, and call :meth:`inject` to read values from the
        context. Unlike ``__init__``, the shared context inherited from the
        parent component is already available when this method runs.
 
        This method is called exactly once per component instance, immediately
        before :meth:`on_mount`. It is not called again when the component
        re-renders or when its props are updated.
 
        There is no need to call ``super().setup()`` — the base implementation
        is a no-op and exists solely to make the method safely overridable.
 
        Example:
            ::
 
                class UserCard(Component[UserCardProps]):
                    def setup(self) -> None:
                        # State initialization
                        self._state = {"expanded": False}
 
                        # Instance attributes
                        self.formatter = DateFormatter()
 
                        # Context access — available here, not in __init__
                        self.theme = self.inject("theme", default="light")
        """
        pass

    @final
    def set_state(self, updates: Mapping[str, Any]) -> None:
        """Updates internal state and schedules a re-render.

        This method merges ``updates`` into the existing ``_state``,
        and then calls ``_schedule_update()`` to trigger a re-render cycle.
        The ``_dirty`` flag prevents multiple calls to ``_schedule_update``
        within a single cycle.

        Called by user code inside event handlers (e.g., ``on_click``, ``on_input``).

        Args:
            updates: Dictionary containing key-value state updates.
                Existing keys will be overwritten, and new keys will be added.
                Example: ``{"count": 5, "loading": True}``.

        Example:
            ::

                def handle_click(self):
                    self.set_state({"count": self._state["count"] + 1})
        """
        if not self._mounted:
            return
        
        # Wrap state update with closure and add it into self._updates for batch state update and render
        def update() -> None:
            # Merge updates into _state (only if _state is a dict).
            if isinstance(self._state, dict):
                self._state.update(updates)

        self._updates.append(update)

        # Prevent rescheduling if an update is already scheduled.
        # Without this guard, multiple calls to set_state() within
        # a single event handler would schedule multiple re-renders.
        if self._dirty:
            return
        self._dirty = True

        self._enqueue_dirty()

    @final
    def execute_update(self) -> None:
        """Executes the scheduled update by calling the bound callback."""
        if not self._updates:
            return

        self._prev_state = dict(self._state or {}).copy()
        self._prev_props = cast(PropsT, dict(self.props or {}).copy())

        while self._updates:
            self._updates.popleft()()

        # Reset flag after the update has been scheduled,
        # so that subsequent calls to set_state() can schedule updates.
        self._dirty = False
        
        # Call the callback bound by _expand_tree() to
        # App._update_from_key(component_key). This will trigger
        # re-render -> diff -> DOM patch.
        self._schedule_update()

    def render(self) -> "VNode":
        """Returns a VNode tree representing the component's UI.

        This method **must be overridden** by every subclass. It is called
        by ``_expand_tree()`` in ``core/app.py`` during the initial render,
        and by ``App._update_from_key()`` during re-renders caused by state changes.

        Returns:
            VNode: The virtual DOM tree describing the current visual state
                of the component.

        Raises:
            NotImplementedError: If the subclass does not override this method.

        Example:
            ::

                def render(self) -> VNode:
                    return h("div", {"class": "card"}, [
                        h("h2", {}, [self.props["title"]]),
                        h("p", {}, [self._state["content"]]),
                    ])
        """
        raise NotImplementedError

    def on_mount(self) -> None:
        """Lifecycle hook called once after the component is first created.

        Override this method to perform initialization that requires the
        DOM to be available, such as fetching data, setting up timers, or
        subscribing to external events.

        Called by ``_expand_tree()`` in ``core/app.py`` after the component
        is instantiated and its VNode tree is expanded.

        Example:
            ::

                def on_mount(self):
                    self.set_state({"data": fetch_initial_data()})
                    # Tidak perlu memanggil super().on_mount()!
        """
        pass

    def on_update(self, prev_props: PropsT, prev_state: dict[str, Any]) -> None:
        """Lifecycle hook called after the component is updated.

        Override this method to perform side effects after the component
        is updated, such as updating the DOM or fetching new data.

        Args:
            prev_props: The previous props of the component.
            prev_state: The previous state of the component.

        Example:
            ::

                def on_update(self, prev_props, prev_state):
                    if prev_props["title"] != self.props["title"]:
                        self.set_state({"content": fetch_new_content()})
        """
        pass

    def on_unmount(self) -> None:
        """Lifecycle hook called when the component is about to be removed from the tree.

        This method is purely for user-defined cleanup operations such as
        canceling timers or unsubscribing from external events.
        You do NOT need to call `super().on_unmount()`. Internal proxy
        cleanups are handled automatically by the framework.

        Called by orphan detection in ``App._update_from_key()`` in ``core/app.py``
        when the component no longer exists in the new tree.

        Example:
            ::

                def on_unmount(self):
                    cancel_my_timer(self.timer_id)
        """
        # Execute all cleanup closures registered by the bridge (e.g., proxy.destroy())
        # to prevent memory leaks.
        pass

    @final
    def _invoke_on_mount(self) -> Any:
        """Internal framework method.
        Sets the internal _mounted flag to True, allowing state updates,
        and then executes the user-defined on_mount hook.
        """
        self._mounted = True
        return self.on_mount()

    @final
    def _invoke_on_unmount(self) -> Any:
        """Internal framework method.
        Executes the user-defined on_unmount hook, updates the _mounted flag,
        and automatically flushes all registered cleanup callbacks (e.g. JS proxies)
        to prevent memory leaks.
        """
        result = self.on_unmount()
        self._mounted = False
        for cleanup in self._cleanups:
            cleanup()
        self._cleanups.clear()
        return result
    
    @final
    def trigger(self, event_name: str, payload: object = None) -> None:
        """
        Send event to parent by callback props.
        Example:    
            ::
            
                trigger("remove", id) → call props["on_remove"](id)
                trigger("toggle")     → call props["on_toggle"]()
        """
        if not self._mounted:
            return

        if event_name not in self.events:
            raise ValueError(f"Event '{event_name}' is not defined in the component's events.")
        
        handler = self.events.get(event_name)
        if callable(handler):
            if payload is None:
                handler()
            else:
                handler(payload)

    @final
    def provide(self, key: str, value: Any) -> None:
        """Provide a context value to descendant components.

        Args:
            key: The unique key identifying the context.
            value: The value to provide to descendants.

        Example:
            ::

                self.provide("theme", "dark")
        """
        self._provided[key] = value
        self._contexts[key] = value

    @final
    def inject(self, key: str, default: Any = None) -> Any:
        """Inject a context value provided by an ancestor component.

        Args:
            key: The unique key identifying the context.
            default: The default value to return if the context is not found.

        Returns:
            The context value provided by an ancestor, or the default value
            if no provider exists for the given key.
        """
        return self._contexts.get(key, default)

    def component_did_catch(self, error: Exception) -> None:
        """Error Boundary hook to capture errors from child components.

        Override this method to handle errors occurring during child component
        rendering. Similar to React's ``componentDidCatch``. The traversal
        logic (finding an ancestor with this hook) is in ``_expand_tree()``
        in ``core/app.py``.

        Args:
            error: The exception thrown by a child component during rendering
                or lifecycle methods.

        Example:
            ::

                def component_did_catch(self, error):
                    self.set_state({"has_error": True, "error_msg": str(error)})
        """
        pass

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        # Warn if __init__ is overridden directly
        if "__init__" in cls.__dict__:
            import warnings
            warnings.warn(
                f"'{cls.__name__}' overrides __init__ — this is not recommended. "
                f"Use setup() instead for state initialization and context access.",
                stacklevel=2,
            )
