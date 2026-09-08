"""Core module of the Pyon-Py application.

This module contains the main entry point of the framework (App class) along with
internal functions for VNode tree expansion, path searching, DOM path synchronization,
and the Error Boundary mechanism.

Main flow:
    1. App.mount() → _expand_tree() → bridge.full_render()        (initial render)
    2. Component.set_state() → App._update_from_key()              (incremental update)
       → _expand_tree() → diff() → bridge.apply_patches()

This module MUST NOT be imported directly by the user — use it through App.
"""

from __future__ import annotations

from collections import deque
from typing import Any, final

from .component import Component
from .utils import current_component, dispatch
from .vnode import Children, VNode


class ErrorCaughtByBoundary(Exception):
    """Internal exception for the Error Boundary mechanism (stack unwinding).

    When a child component throws an exception during render, the exception
    will be wrapped in ErrorCaughtByBoundary and re-raised up the parent chain
    until it finds a boundary component — which is a component that overrides the
    ``component_did_catch`` method.

    Once it reaches the boundary, the exception is caught, ``component_did_catch``
    is called with the original error, and then the boundary re-renders with the
    fallback UI.

    Used in:
        - ``_expand_tree()`` — when catching exceptions from rendering child components
        - ``_expand_tree()`` — when detecting a boundary and wrapping the error

    Args:
        boundary_key: Hierarchical full key of the boundary component that will
            handle the error. Example: ``"TodoApp.error-boundary"``.
        original_error: The original exception thrown by the child component.

    Examples:
        >>> raise ErrorCaughtByBoundary("App.boundary", ValueError("empty data"))
    """

    def __init__(self, boundary_key: str, original_error: Exception):
        self.boundary_key = boundary_key
        self.original_error = original_error


def _check_sibling_keys(children: Children):
    from collections import Counter

    component_children = [
        child for child in children
        if isinstance(child, VNode)
        and isinstance(child.tag, type)
        and issubclass(child.tag, Component)
    ]

    for child in component_children:
        if not child.key and isinstance(child.tag, type):
            child.key = child.tag.__name__

    key_counts = Counter(child.key for child in component_children)
    duplicate_keys = {key for key, count in key_counts.items() if count > 1 and isinstance(key, str)}

    if duplicate_keys:
        raise ValueError(
            f"Duplicate keys found in the same level of the VNode tree:\n"
            f"{sorted(duplicate_keys)}."
            f"Add explicit unique 'key' props to the components."
            f"Example: h('TodoItem', {{\"key\": \"todo-item-1\"}})"
        )


def _expand_tree(
    node: VNode,
    path: str,
    parent_key: str,
    component_map: dict[str, Component],
    app: App,
) -> VNode:
    """Recursively expands a VNode tree into a pure HTML tree.

    This is a CORE function of the framework. It converts a VNode tree that
    may contain Component classes as tags into a pure VNode tree (where all
    tags are HTML strings), ready for diffing and full rendering.

    Main responsibilities:
        - Instantiate new components or reuse old instances (based on key)
        - Lifecycle: call ``on_mount()`` for new components
        - Bind the ``_schedule_update`` closure to the instance
        - Store ``_dom_path`` on the instance for DOM targeting
        - Slot pattern: inject ``node.children`` into ``props["children"]``
        - Error Boundary: try/except with upward stack unwinding

    Called by:
        - ``App.mount()`` — during initial render (initial mount)
        - ``App._update_from_key()`` — during incremental re-render

    Args:
        node: The VNode to be expanded. Its tag can be an HTML string
            (e.g., ``"div"``) or a Component class (e.g., ``TodoItem``).
        path: The current DOM path in a dot-separated index format.
            Example: ``"0"`` (root), ``"0.1.3"`` (3rd child of the 1st child).
        parent_key: The hierarchical full key of the nearest parent component.
            Example: ``"TodoApp"`` or ``"TodoApp.error-boundary"``.
            An empty string ``""`` if there is no parent component yet.
        component_map: A dictionary mapping full_key → Component instance.
            Used to reuse existing instances (preserving state).
        app: Reference to the App instance — needed for binding the
            ``_schedule_update`` closure.

    Returns:
        A new VNode with all tags as HTML strings (no Component classes).
        This VNode is ready to be diffed or rendered to the DOM.

    Raises:
        ValueError: If the component does not have a ``key`` prop.
        ErrorCaughtByBoundary: If an error occurs and a boundary is found
            in the parent chain (will be caught by the recursive caller).
        Exception: If an error occurs and no boundary is found.
    """
    # ── CASE 1: Tag is a Component class ──────────────────────────────
    if isinstance(node.tag, type) and issubclass(node.tag, Component):
        # Get local key from props — mandatory for all custom components.
        # Key is used as a unique identifier for the component in component_map.
        local_key = node.props.get("key") or node.tag.__name__
        if local_key is None:
            raise ValueError(
                f"'{node.tag.__name__}' must have 'key' props. "
                f'Example: h({node.tag.__name__}, {{"key": "unique-name"}})'
            )
        local_key = str(local_key)

        # Build hierarchical full key from parent_key + local_key.
        # Format: "TodoApp.error-boundary.todo-item-1"
        # Full key ensures global uniqueness even if local_key is the same at different levels.
        full_key = f"{parent_key}.{local_key}" if parent_key else local_key

        # Inject children into props so it can be used with the Slot pattern.
        # Create a copy of props to avoid mutating the original VNode props.
        if node.children:
            props = {**node.props, "children": list(node.children)}
        else:
            props = node.props.copy()

        instance: Component | None = None
        try:
            # ── Reuse or create new instance based on key existence ──
            if full_key in component_map:
                # Re-render: reuse the old instance (state remains preserved),
                # only update props that might change from the parent.
                instance = component_map[full_key]
                instance._prev_props = instance.props.copy()
                instance._prev_state = instance._state.copy()

                instance.props = props  # type: ignore

                if parent_key and parent_key in component_map:
                    instance._contexts = component_map[parent_key]._contexts.copy()
                else:
                    instance._contexts = app._contexts.copy()
                instance._contexts.update(instance._provided)

                app.pending_updates.append(instance)
            else:
                # Initial render: create a new instance, call on_mount(),
                # and save it to component_map.
                instance = node.tag(props)

                if parent_key and parent_key in component_map:
                    instance._contexts = component_map[parent_key]._contexts.copy()
                else:
                    instance._contexts = app._contexts.copy()
                instance._contexts.update(instance._provided)
                instance.setup()

                # Connect _schedule_update with a closure that captures
                # full_key. When the component calls set_state(), this
                # closure will be called → App._update_from_key(full_key).
                # Lambda with default argument (k=full_key) ensures
                # each instance gets its own key (late binding issue).
                instance._schedule_update = lambda k=full_key: app._update_from_key(k)
                instance._enqueue_dirty = lambda c=instance: app.schedule_flush(c)

                dispatch(instance._invoke_on_mount(), instance)
                component_map[full_key] = instance

            # Store the current DOM path in the instance.
            # Used by _sync_dom_paths() and App._update_from_key()
            # to determine the position of the subtree in the DOM.
            instance._dom_path = path

            # Expand the render output of the component at the SAME path.
            # Components do not add a path level — the path belongs to its root DOM node.
            # For example: component at path "0.1" → render() produces <div>
            # → that <div> remains at path "0.1".
            token = current_component.set(instance)
            try:
                child_vnode = instance.render()
            finally:
                current_component.reset(token)
                
            expanded = _expand_tree(child_vnode, path, full_key, component_map, app)

            # Mark the expanded VNode with the component's full_key.
            # Used by _find_path_by_key() and _collect_keys_in_tree().
            expanded.component_key = full_key
            expanded.key = node.key
            return expanded

        except ErrorCaughtByBoundary as e_boundary:
            # ── Error Boundary: catch if we are the boundary target ──
            # ErrorCaughtByBoundary goes up through recursion until it finds the
            # targeted boundary component (e_boundary.boundary_key).
            if full_key == e_boundary.boundary_key:
                if not instance:
                    raise RuntimeError("ErrorCaughtByBoundary: instance is None")

                # We are the boundary target — call component_did_catch
                # to update state (e.g., set fallback flag).
                instance.component_did_catch(e_boundary.original_error)

                # Execute any state updates scheduled during component_did_catch synchronously
                # before rendering the fallback UI.
                while instance._updates:
                    instance._updates.popleft()()
                instance._dirty = False

                # Re-render with new state (fallback UI).
                token = current_component.set(instance)
                try:
                    child_vnode = instance.render()
                finally:
                    current_component.reset(token)
                expanded = _expand_tree(child_vnode, path, full_key, component_map, app)
                expanded.component_key = full_key
                expanded.key = node.key
                return expanded
            else:
                # Not our boundary — propagate upwards (stack unwinding).
                raise

        except Exception as e:
            # ── Error Boundary Traversal ─────────────────────────────────
            # Standard exception from child render(). Find the nearest boundary
            # in the parent chain by traversing the hierarchical key upwards.
            boundary_key = None
            curr_key = parent_key

            # Upward traversal: "A.B.C" → "A.B" → "A" → ""
            while curr_key:
                parent_instance = component_map.get(curr_key)

                # Check if parent overrides component_did_catch
                # (not the default from the base Component class).
                if (
                    parent_instance
                    and type(parent_instance).component_did_catch
                    is not Component.component_did_catch
                ):
                    boundary_key = curr_key
                    break

                # Go up one level to parent: "A.B.C" → "A.B"
                if "." in curr_key:
                    curr_key = curr_key.rsplit(".", 1)[0]
                else:
                    curr_key = ""

            if boundary_key:
                # Boundary found — wrap the error and throw it upwards.
                # This exception will be caught by the ErrorCaughtByBoundary
                # except block at the appropriate recursion level.
                raise ErrorCaughtByBoundary(boundary_key, e)
            else:
                # No boundary — throw the original error (unhandled).
                raise e

    _check_sibling_keys(node.children)

    # ── CASE 2: HTML string tag — expand children only ──────────────────
    expanded_children = []
    for i, child in enumerate(node.children):
        if isinstance(child, VNode):
            # Recursively expand child VNode with path appended by index.
            # "0.1" + child index 3 → "0.1.3"
            expanded_children.append(
                _expand_tree(child, f"{path}.{i}", parent_key, component_map, app)
            )
        else:
            # Child is not a VNode (text string, number, etc.) — pass as is.
            expanded_children.append(child)

    # Return a new VNode with expanded children.
    # Do not mutate the original node so the old tree remains intact for diffing.
    return VNode(
        tag=node.tag,
        props=node.props,
        children=expanded_children,
        key=node.key,
        _owner=node._owner,
    )


def _find_path_by_key(
    tree: VNode,
    target_key: str,
    current_path: str = "0",
) -> str | None:
    """Finds the DOM path of a VNode that has a specific component_key.

    Traverses the expanded VNode tree recursively (DFS) to find the VNode
    whose ``component_key`` matches the ``target_key``.

    Since the expanded tree only contains HTML string tags, component_key is stored
    when ``_expand_tree()`` renders the component. Alternatively, it can also
    lookup directly from ``component_map[key]._dom_path`` — this function is
    available as a traversal fallback.

    Called by:
        - ``_sync_dom_paths()`` — to synchronize the ``_dom_path`` of all
          instances after the tree changes.

    Args:
        tree: The root VNode of the expanded tree to be traversed.
        target_key: The hierarchical full key of the searched component.
            Example: ``"TodoApp.error-boundary.todo-item-1"``.
        current_path: The current DOM path in the traversal.
            Defaults to ``"0"`` (root). Incremented as it goes down levels,
            e.g., ``"0.1.3"``.

    Returns:
        The DOM path string if found (e.g., ``"0.2.1"``), or ``None`` if not
        found in the tree.
    """
    # Check if this node has a matching component_key.
    if getattr(tree, "component_key", None) == target_key:
        return current_path

    # Recursively traverse children (depth-first search).
    for i, child in enumerate(tree.children):
        if isinstance(child, VNode):
            result = _find_path_by_key(child, target_key, f"{current_path}.{i}")
            if result is not None:
                return result

    return None


def _collect_keys_in_tree(node: VNode, result: set) -> None:
    """Collects all component_keys from an expanded VNode tree.

    Recursively traverses the tree and adds every ``component_key`` found
    into the ``result`` set. The ``component_key`` is set by ``_expand_tree()``
    when rendering components.

    Called by:
        - ``App._update_from_key()`` — to detect orphan components.
          Orphans are components that exist in ``component_map`` before
          re-rendering but do not exist in the new tree after re-rendering.
          Orphan components will be unmounted.

    Args:
        node: The root VNode of the expanded tree to be traversed.
        result: The set to be filled with the found component_keys.
            Must be initialized by the caller (e.g., ``set()``).
            Modified in-place.
    """
    # Add the key of this node if it exists (only VNodes originating from
    # components have a component_key).
    if node.component_key is not None:
        result.add(node.component_key)

    # Recursively go to all children that are VNodes.
    for child in node.children:
        if isinstance(child, VNode):
            _collect_keys_in_tree(child, result)


def _get_vnode_by_path(tree: VNode, path: str) -> VNode:
    """Navigates to the VNode at a specific path in the expanded tree.

    The path uses a dot-separated index format: ``"0"`` for root,
    ``"0.1.3"`` for the 3rd child of the 1st child of the root. The first
    part (``"0"``) is always the root and is skipped during navigation.

    Called by:
        - ``App._update_from_key()`` — to get the old subtree
          (old branch) to be diffed with the new subtree.

    Args:
        tree: The root VNode of the expanded tree.
        path: The target DOM path in a dot-separated index format.
            Example: ``"0"`` (root), ``"0.2.1"`` (1st child of the 2nd
            child of the root).

    Returns:
        The VNode located at the requested path.

    Raises:
        TypeError: If a child along the traversed path is not a VNode
            (e.g., a text string).
        IndexError: If an index in the path exceeds the number of children.
    """
    parts = path.split(".")
    node = tree

    # Skip the first part ("0" = root) since the tree is already the root.
    for part in parts[1:]:
        idx = int(part)
        child = node.children[idx]
        if not isinstance(child, VNode):
            raise TypeError(f"Expected VNode, got {type(child)}")
        node = child

    return node


def _set_vnode_by_path(tree: VNode, path: str, new_node: VNode) -> None:
    """Replaces a VNode at a specific path in-place within its parent.

    This function navigates to the parent of the target path, then replaces the
    child at the last index with ``new_node``. The mutation is done directly
    on the parent's ``children`` list.

    Called by:
        - ``App._update_from_key()`` — to update ``current_tree`` after patching.
          The old subtree is replaced by the new expanded subtree.

    Notes:
        If ``path`` is ``"0"`` (root), this function does nothing because the root
        does not have a parent. This case is handled directly by
        ``App._update_from_key()`` which replaces ``self.current_tree``.

    Args:
        tree: The root VNode of the expanded tree to be modified.
        path: The target DOM path to be replaced, in dot-separated
            index format. Example: ``"0.2.1"``.
        new_node: The new VNode to replace the old VNode at the path.

    Raises:
        TypeError: If a child along the traversed path is not a VNode,
            or if ``node.children`` is not a list.
    """
    parts = path.split(".")

    if len(parts) == 1:
        # Path "0" — the root itself, cannot be replaced in-place.
        # Handled by the caller (App._update_from_key replaces current_tree).
        return

    # Navigate to the parent of the target node.
    # For path "0.1.3" → navigate to the node at "0.1", then replace children[3].
    node = tree
    for part in parts[1:-1]:
        child = node.children[int(part)]
        if not isinstance(child, VNode):
            raise TypeError(f"Expected VNode, got {type(child)}")
        node = child

    # Replace the child at the last index (in-place mutation).
    last_idx = int(parts[-1])
    # VNode.children is type-annotated as Sequence, but at runtime it is
    # always a list (mutable), so direct assignment is safe.
    if isinstance(node.children, list):
        node.children[last_idx] = new_node
    else:
        raise TypeError("node.children is not a list")


def _sync_dom_paths(
    tree: VNode,
    component_map: dict[str, Component],
    current_path: str = "0",
) -> None:
    """Synchronizes the ``_dom_path`` of all component instances after the tree changes.

    After ``current_tree`` is updated (e.g., via ``_set_vnode_by_path``),
    the DOM position of components might change (children reordered/removed).
    This function updates the ``_dom_path`` of each instance in ``component_map``
    to match its new position in the tree.

    This is crucial to ensure that the next ``_update_from_key()`` targets
    the correct DOM path.

    Called by:
        - ``App._update_from_key()`` — at the end of the update cycle, after
          patching and subtree replacement.

    Args:
        tree: The root VNode of the updated expanded tree.
        component_map: Dictionary of full_key → Component instance.
            Each instance will have its ``_dom_path`` updated.
        current_path: The initial DOM path for traversal (defaults to ``"0"``).
            This parameter exists for signature consistency but is not
            directly used — search is done via ``_find_path_by_key()``.
    """

    # Iterate all instances in component_map and find their new positions
    # in the tree using _find_path_by_key().
    for key, instance in component_map.items():
        new_path = _find_path_by_key(tree, key)
        if new_path is not None:
            instance._dom_path = new_path


@final
class App:
    """Single entry point of the Pyon-Py framework.

    This class manages the entire application lifecycle: from the initial render
    (mount) to incremental updates when component state changes.
    Each application has only one App instance.

    Attributes:
        root_class: The root component class to be rendered.
        current_tree: The expanded VNode tree (pure HTML).
            Represents the current virtual DOM state.
        component_map: A dictionary mapping full_key to Component instances.
            Enables instance reuse (preserving state).
        selector: CSS selector for the target mount element in the DOM.

    Work flow:
        1. ``App(RootComponent)`` — initialization with the root class.
        2. ``app.mount("#app")`` — initial render to the DOM.
        3. Component calls ``set_state()`` → ``_schedule_update()``
           → ``_update_from_key()`` — incremental update.

    Args:
        root_component_class: Root component class (not an instance).
            Example: ``App(TodoApp)`` not ``App(TodoApp({}))``.

    Examples:
        >>> from pyon.core import App
        >>> from components.todo import TodoApp
        >>> app = App(TodoApp)
        >>> app.mount("#app")
    """

    def __init__(self, root_component_class: type[Component]) -> None:
        # Root component class — will be instantiated during mount().
        self.root_class: type[Component] = root_component_class

        # Latest expanded VNode tree (all HTML string tags).
        # None before mount() is called.
        self.current_tree: VNode | None = None

        # Map of full_key → Component instance.
        # Allows instance reuse during re-render (state preserved).
        # Key format: "TodoApp.error-boundary.todo-item-1"
        self.component_map: dict[str, Component] = {}

        self.pending_updates: deque[Component] = deque()
        self.dirty_components: deque[Component] = deque()

        # CSS selector of the DOM element where the app is mounted.
        self.selector: str = "#app"

        # Flag to prevent multiple flushes in a single cycle.
        self._flush_scheduled = False

        self._contexts: dict[str, Any] = {}

    def mount(self, selector: str = "#app") -> None:
        """Performs initial rendering of the application to the DOM (initial mount).

        Process:
            1. Create a temporary VNode with tag = root_class.
            2. Expand the tree via ``_expand_tree()`` → produces HTML VNode tree.
            3. Send the tree to the bridge's ``full_render()`` to be rendered to the DOM.

        After mounting, ``current_tree`` and ``component_map`` are populated.
        All components have received their ``on_mount()`` and ``_schedule_update``.

        Args:
            selector: CSS selector of the target DOM element. Defaults to ``"#app"``.
                This element must already exist on the HTML page.

        Raises:
            ValueError: If the root component does not have a ``key`` prop
                (caught in ``_expand_tree()``).
        """
        from pyon.dom import full_render

        self.selector = selector

        # Create a temporary VNode for the root component.
        # Default key = class name (e.g., "TodoApp").
        # This VNode will be expanded by _expand_tree() into an HTML tree.
        self.current_tree = _expand_tree(
            VNode(
                tag=self.root_class,
                props={"key": self.root_class.__name__},
                children=[],
            ),
            path="0",  # Root is always at path "0"
            parent_key="",  # No parent yet
            component_map=self.component_map,
            app=self,
        )

        # Send the expanded tree to the bridge to be rendered to the DOM.
        # full_render() converts VNode tree → HTML string → innerHTML.
        full_render(
            self.current_tree,
            selector,
            self.flush_updates,
            component_map=self.component_map,
        )

    def _update_from_key(self, key: str) -> None:
        """Incremental update cycle for a specific component.

        Called by ``Component._schedule_update()`` (closure bound in
        ``_expand_tree()``). This function only re-renders the subtree
        at the component's DOM path, then performs diff + patch.

        Flow:
            1. Get instance and DOM path from ``component_map``.
            2. Snapshot child keys before re-rendering (for orphan detection).
            3. ``_expand_tree()`` — expand new subtree.
            4. ``_collect_keys_in_tree()`` — collect keys in the new tree.
            5. Calculate orphan keys (exist in snapshot, missing in new tree).
            6. ``diff()`` — compare old branch vs new branch → patches.
            7. Unmount orphan components (call ``on_unmount()``).
            8. ``apply_patches()`` — send patches to bridge (DOM update).
            9. Update ``current_tree`` with the new subtree.
            10. ``_sync_dom_paths()`` — synchronize ``_dom_path`` of all instances.

        Orphan detection strategy:
            Orphan = component that exists in ``component_map`` before re-rendering
            but disappears in the new tree. This happens when conditional rendering
            removes a child component. Orphans will be unmounted and removed from
            ``component_map``.

        Args:
            key: Hierarchical full key of the component triggering the update.
                Example: ``"TodoApp.todo-list.todo-item-1"``.
        """
        from pyon.dom import apply_patches

        from .differ import diff

        # Guard: do not process if the tree has not been mounted yet.
        if self.current_tree is None:
            return

        # Guard: do not process if the component has been unmounted (orphaned).
        instance = self.component_map.get(key)
        if instance is None:
            return

        # Get DOM path from the instance — set by _expand_tree().
        path = instance._dom_path

        # ── Snapshot child keys before re-rendering ──────────────────────
        # Collect all keys that are descendants of this component.
        # Example: key="App" → retrieve "App.list", "App.list.item-1", etc.
        keys_before = {k for k in self.component_map if k.startswith(key + ".")}

        # ── Expand new subtree ───────────────────────────────────────────
        # Render component and expand the output into an HTML VNode tree.
        token = current_component.set(instance)
        try:
            rendered_vnode = instance.render()
        finally:
            current_component.reset(token)
        new_branch = _expand_tree(
            rendered_vnode,
            path=path,
            parent_key=key,
            component_map=self.component_map,
            app=self,
        )

        # ── Orphan detection ─────────────────────────────────────────────
        # Collect keys present in the new tree, then compare
        # with the snapshot. Missing keys = orphans.
        keys_in_new = set()
        _collect_keys_in_tree(new_branch, keys_in_new)
        orphan_keys = keys_before - keys_in_new

        # ── Diff old branch vs new branch ────────────────────────────────
        old_branch = _get_vnode_by_path(self.current_tree, path)

        # Bug Fix: Pastikan new_branch mempertahankan identitas (key & component_key)
        # dari VNode sebelumnya. Jika hilang, differ akan menganggap ini elemen baru
        # dan menghancurkan referensi DOM proxy secara prematur.
        new_branch.key = old_branch.key
        new_branch.component_key = old_branch.component_key

        patches = diff(old_branch, new_branch, path)

        # ── Unmount orphan components ────────────────────────────────────
        # Call on_unmount() and remove from component_map.
        # This ensures no memory leaks or stale references.
        for orphan_key in orphan_keys:
            if orphan_key in self.component_map:
                dispatch(
                    self.component_map[orphan_key]._invoke_on_unmount(),
                    self.component_map[orphan_key],
                )
                del self.component_map[orphan_key]

        # ── Apply patches to DOM via bridge ──────────────────────────────
        if patches:
            apply_patches(
                patches,
                self.selector,
                flush_callback=self.flush_updates,
                component_map=self.component_map,
            )

        # ── Update current_tree ──────────────────────────────────────────
        if path == "0":
            # Root — replace the entire tree.
            self.current_tree = new_branch
        else:
            # Non-root — replace the subtree at the specific path (in-place mutation).
            _set_vnode_by_path(self.current_tree, path, new_branch)

        # ── Synchronize _dom_path of all instances ───────────────────────
        # After the tree changes, the DOM position of components might shift.
        # Ensure all instances have an up-to-date _dom_path.
        _sync_dom_paths(self.current_tree, self.component_map)
        dispatch(
            instance.on_update(instance._prev_props, instance._prev_state), instance
        )
        while self.pending_updates:
            instance = self.pending_updates.popleft()
            dispatch(
                instance.on_update(instance._prev_props, instance._prev_state), instance
            )

    def flush_updates(self) -> None:
        """Flushes all pending updates and re-renders the entire tree."""
        self._flush_scheduled = False
        iteration_count = 0
        max_iterations = 100  # Prevent infinite loops in case of circular updates

        while self.dirty_components:
            iteration_count += 1
            if iteration_count > max_iterations:
                self.dirty_components.clear()
                raise RuntimeError(
                    "PyOn-Py Error: Maximum update depth exceeded (100 iterations)."
                    "This may happen when a component uncontrollably calls set_state()"
                    "in its on_update(), on_mount(), or render() methods."
                )

            comp = self.dirty_components.popleft()
            if comp._dirty and comp._mounted:
                comp.execute_update()

    def provide(self, key: str, value: Any) -> None:
        """Provide a context value to descendant components.

        Args:
            key: The unique key identifying the context.
            value: The value to provide to descendants.

        Example:
            ::

                self.provide("theme", "dark")
        """
        self._contexts[key] = value

    def schedule_flush(self, comp: Component) -> None:
        self.dirty_components.append(comp)
        if not self._flush_scheduled:
            self._flush_scheduled = True
            self._request_microtask_flush()

    def _request_microtask_flush(self) -> None:
        try:
            from pyon.dom import queue_microtask

            queue_microtask(self._run_flush)
        except (ImportError, AttributeError, NameError, Exception):
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.call_soon(self._run_flush)
            except RuntimeError:
                pass

    def _run_flush(self) -> None:
        self._flush_scheduled = False
        self.flush_updates()


_active_app: App | None = None


def create_app(root_component_class: type[Component]) -> App:
    global _active_app
    app = App(root_component_class)
    _active_app = app
    return app


def teardown() -> None:
    global _active_app
    if _active_app:
        # Unmount all active components
        for comp in _active_app.component_map.values():
            try:
                comp._invoke_on_unmount()
            except Exception as e:
                import traceback

                print(f"Error unmounting {comp}: {e}")
                traceback.print_exc()

        _active_app.component_map.clear()
        _active_app.dirty_components.clear()

        # Destroy global contexts (e.g., Router) to prevent memory/event leaks
        for val in _active_app._contexts.values():
            if hasattr(val, "destroy") and callable(val.destroy):
                try:
                    val.destroy()
                except Exception as e:
                    print(f"Error destroying context {val}: {e}")

        _active_app._contexts.clear()
        _active_app = None
