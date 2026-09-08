"""Virtual Node (VNode) module — the basic building block of the Virtual DOM tree.

This module defines the VNode data structure and the type aliases used
throughout the Pyon-Py codebase. A VNode represents a single element in the
virtual DOM tree, similar to the concept of a React Element.

Example usage::

    tree = h("div", {"class": "container"}, [
        h("h1", {}, ["Hello World"]),
        h("p", {}, ["First paragraph"]),
    ])
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, TypeAlias, Union, TYPE_CHECKING

from .events import EventHandler
from .utils import current_component

if TYPE_CHECKING:
    from .component import Component

# --- Type Aliases ---
# These aliases are used throughout the codebase (differ.py, app.py, pyodide_impl.py, etc.)

# TagType: can be an HTML string tag ("div", "span", "button") or a Component class.
# Used by _expand_tree() in core/app.py to determine whether a node
# needs to be instantiated as a Component or directly as a DOM element.
TagType: TypeAlias = str | type

# Children: list of child nodes of a VNode.
# Can contain other VNodes (for nested elements) or primitives (str/int/float)
# that will be rendered as text nodes.
Children: TypeAlias = Sequence[Union["VNode", str, int, float]]

# PropValue: a valid value for a single property.
# Supports strings, numbers, booleans, event handlers, dictionaries (e.g. for style), or None.
PropValue: TypeAlias = str | int | float | bool | EventHandler | Children | None | dict[str, Any] | object

# Props: dictionary of properties passed to an element/component.
# Example: {"class": "active", "on_click": handler_fn, "disabled": True}
Props: TypeAlias = dict[str, PropValue]


@dataclass
class VNode:
    """Representation of a single node in the Virtual DOM tree.

    VNode is the fundamental unit that makes up the UI tree. Each VNode
    represents a single HTML element or a Component instance.

    Attributes:
        tag: Element type. Can be an HTML tag string (e.g. ``"div"``,
            ``"button"``) or a reference to a Component class (e.g. ``TodoItem``).
            Used by ``_expand_tree()`` in ``core/app.py`` to decide the rendering method.
        props: Dictionary of properties/attributes for this element.
            Example: ``{"class": "card", "id": "main", "on_click": handler}``.
            Processed by ``_apply_props()`` in ``pyodide_impl.py`` during DOM element
            creation/update.
        children: List of child nodes. Can contain other VNodes or primitive values
            (str, int, float) which will become text nodes.
        key: Local key for keyed reconciliation in ``core/differ.py``.
            Helps the differ match old and new nodes efficiently when the list of
            children changes (e.g., when items are added/removed from a list).
            If not set explicitly, it will be retrieved from ``props["key"]`` in
            ``__post_init__()``.
        component_key: Full hierarchical key set by ``_expand_tree()`` in
            ``core/app.py``. Format: ``"ParentKey.local_key"``
            (e.g., ``"TodoApp.todo-item-1"``). Used by:
            - ``_find_path_by_key()`` for DOM path synchronization.
            - ``_collect_keys_in_tree()`` for orphan component detection.

    Example:
        >>> node = VNode(
        ...     tag="div",
        ...     props={"class": "wrapper"},
        ...     children=[VNode(tag="span", children=["text"])],
        ...     key="wrapper-1",
        ... )
    """

    tag: TagType
    props: Props = field(default_factory=dict)
    children: Children = field(default_factory=list)
    key: str | None = None
    component_key: str | None = None
    _owner: Component | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Automatic initialization after the dataclass is created.

        If ``key`` has not been explicitly set but ``"key"`` exists in ``props``,
        its value will be retrieved from there. This allows users to write
        ``h("li", {"key": "item-1"}, [...])`` without having to set the ``key``
        parameter separately.

        Called automatically by the Python dataclass mechanism.
        """
        if self.key is None and "key" in self.props:
            # Retrieve key from props for consistency — users only need to
            # set the key in props (similar to React patterns).
            self.key = str(self.props["key"])


def h(
    tag: TagType,
    props: Props | None = None,
    children: Children | None = None,
) -> VNode:
    """Helper function to create a VNode — equivalent to JSX in React.

    This function is the primary way to construct the Virtual DOM tree inside
    the ``Component.render()`` method. The name ``h`` follows the hyperscript
    convention common in UI frameworks.

    Args:
        tag: HTML element tag (e.g. ``"div"``, ``"input"``) or
            Component class (e.g. ``TodoItem``).
        props: Dictionary of properties/attributes. Defaults to ``None`` (will
            be an empty dict). Example: ``{"class": "btn", "on_click": fn}``.
        children: List of child nodes. Defaults to ``None`` (will be an empty
            list). Example: ``["Text", h("span", {}, ["bold"])]``.

    Returns:
        VNode: A new VNode instance ready to be integrated into the virtual DOM tree.

    Example:
        Used inside ``Component.render()``::

            def render(self) -> VNode:
                return h("div", {"class": "container"}, [
                    h("h1", {}, [self._state["title"]]),
                    h(ChildComponent, {"data": self._state["items"]}),
                ])
    """
    owner = current_component.get()
    return VNode(tag=tag, props=props or {}, children=children or [], _owner=owner)
