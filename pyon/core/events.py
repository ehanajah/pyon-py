from __future__ import annotations
from typing import Any, Callable, Coroutine, Protocol, Optional, TypeAlias, Union


class EventTarget(Protocol):
    """
    Protocol for a target that receives events and has listeners for those events.
    """
    value: str
    checked: bool
    name: str
    id: str
    className: str
    
    def getAttribute(self, name: str) -> Optional[str]:
        """Retrieves an attribute from the element."""
        ...
        
    def setAttribute(self, name: str, value: str) -> None:
        """Sets an attribute on the element."""
        ...
        
    def removeAttribute(self, name: str) -> None:
        """Removes an attribute from the element."""
        ...


class DataTransfer(Protocol):
    """
    Protocol for the DataTransfer object used during drag and drop operations.
    """
    dropEffect: str
    effectAllowed: str
    files: Any
    items: Any
    types: Any
    
    def getData(self, format: str) -> str:
        """Retrieves the dragged data for a given format."""
        ...
        
    def setData(self, format: str, data: str) -> None:
        """Sets the data for a drag and drop operation."""
        ...
        
    def clearData(self, format: Optional[str] = None) -> None:
        """Clears the transfer data for the given format."""
        ...
        
    def setDragImage(self, image: Any, x: float, y: float) -> None:
        """Sets a custom image for the drag."""
        ...


# ============================================================================
# Base Event
# ============================================================================

class Event(Protocol):
    """
    Base protocol for all DOM events.
    """
    type: str
    target: EventTarget
    currentTarget: EventTarget
    bubbles: bool
    cancelable: bool
    composed: bool
    defaultPrevented: bool
    eventPhase: int
    isTrusted: bool
    timeStamp: float
    
    def preventDefault(self) -> None:
        """Prevents the event's default action."""
        ...
        
    def stopPropagation(self) -> None:
        """Stops the event from propagating to parent elements."""
        ...
        
    def stopImmediatePropagation(self) -> None:
        """Immediately stops propagation and prevents other listeners from being called."""
        ...


# ============================================================================
# Pointer & Mouse Events
# ============================================================================

class MouseEvent(Event, Protocol):
    """
    Protocol for events related to pointing devices such as the mouse
    (click, dblclick, mousedown, mouseup, mousemove, mouseenter, mouseleave, mouseover, mouseout).
    """
    clientX: float
    clientY: float
    offsetX: float
    offsetY: float
    pageX: float
    pageY: float
    screenX: float
    screenY: float
    movementX: float
    movementY: float
    button: int        # 0 = left, 1 = middle, 2 = right
    buttons: int       # bitmask of buttons currently pressed
    detail: int
    ctrlKey: bool
    shiftKey: bool
    altKey: bool
    metaKey: bool
    relatedTarget: Optional[EventTarget]
    
    def getModifierState(self, keyArg: str) -> bool:
        """Returns the state of a modifier key (Ctrl, Shift, Alt, etc.)."""
        ...


class PointerEvent(MouseEvent, Protocol):
    """
    Protocol for device pointer events
    (pointerdown, pointerup, pointermove, pointerenter, pointerleave, pointerover, pointerout,
    pointercancel, gotpointercapture, lostpointercapture).
    """
    pointerId: int
    width: float
    height: float
    pressure: float
    tangentialPressure: float
    tiltX: float
    tiltY: float
    twist: float
    pointerType: str     # "mouse", "pen", or "touch"
    isPrimary: bool
    
    def getCoalescedEvents(self) -> Any:
        """Gets an array of all coalesced PointerEvents."""
        ...
        
    def getPredictedEvents(self) -> Any:
        """Gets an array of PointerEvents predicted to occur."""
        ...


class WheelEvent(MouseEvent, Protocol):
    """
    Protocol for rotation of a pointing device's wheel.
    """
    deltaX: float
    deltaY: float
    deltaZ: float
    deltaMode: int     # 0 = pixel, 1 = line, 2 = page


class DragEvent(MouseEvent, Protocol):
    """
    Protocol for drag and drop interactions
    (drag, dragstart, dragend, dragenter, dragleave, dragover, drop).
    """
    dataTransfer: Optional[DataTransfer]


# ============================================================================
# Keyboard & Input Events
# ============================================================================

class KeyboardEvent(Event, Protocol):
    """
    Protocol for events related to keyboard interaction
    (keydown, keyup, keypress).
    """
    key: str             # e.g.: "a", "Enter", "ArrowUp"
    code: str            # e.g.: "KeyA", "Enter", "ArrowUp"
    location: int        # 0 = standard, 1 = left, 2 = right, 3 = numpad
    ctrlKey: bool
    shiftKey: bool
    altKey: bool
    metaKey: bool
    repeat: bool
    isComposing: bool
    
    def getModifierState(self, keyArg: str) -> bool:
        """Returns the state of a modifier key (Ctrl, Shift, Alt, etc.)."""
        ...


class InputEvent(Event, Protocol):
    """
    Protocol for data input events on form elements
    (input, beforeinput).
    """
    data: Optional[str]
    inputType: str
    isComposing: bool
    dataTransfer: Optional[DataTransfer]


class CompositionEvent(Event, Protocol):
    """
    Protocol for IME (Input Method Editor) composition events
    (compositionstart, compositionupdate, compositionend).
    """
    data: str
    locale: str


# ============================================================================
# Form Events
# ============================================================================

class ChangeEvent(Event, Protocol):
    """
    Protocol for change events on a form or input (change).
    Used for <select>, <input type='checkbox'>, <input type='radio'>.
    For <input type='text'>, use InputEvent.
    """
    target: EventTarget


class SubmitEvent(Event, Protocol):
    """
    Protocol for form submission events (submit).
    Always call preventDefault() to prevent the page from reloading.
    """
    submitter: Optional[EventTarget]    # the button that triggered submission

    def preventDefault(self) -> None:
        """Prevents the default submit action that reloads the page."""
        ...


class FormDataEvent(Event, Protocol):
    """
    Protocol for form data preparation and submission events (formdata).
    """
    formData: Any


# ============================================================================
# Focus Events
# ============================================================================

class FocusEvent(Event, Protocol):
    """
    Protocol for focus events (focus, blur, focusin, focusout).
    """
    relatedTarget: Optional[EventTarget]


# ============================================================================
# Touch Events
# ============================================================================

class Touch(Protocol):
    """
    Protocol representing a single point of contact on a touch screen.
    """
    identifier: int
    target: EventTarget
    screenX: float
    screenY: float
    clientX: float
    clientY: float
    pageX: float
    pageY: float
    radiusX: float
    radiusY: float
    rotationAngle: float
    force: float


class TouchList(Protocol):
    """
    Protocol representing a list of Touch objects.
    """
    length: int
    
    def item(self, index: int) -> Optional[Touch]:
        """Retrieves the Touch item at the given index."""
        ...


class TouchEvent(Event, Protocol):
    """
    Protocol for touch screen events (touchstart, touchmove, touchend, touchcancel).
    """
    ctrlKey: bool
    shiftKey: bool
    altKey: bool
    metaKey: bool
    touches: TouchList
    targetTouches: TouchList
    changedTouches: TouchList


# ============================================================================
# CSS Animation & Transition Events
# ============================================================================

class AnimationEvent(Event, Protocol):
    """
    Protocol for CSS animation events
    (animationstart, animationend, animationiteration, animationcancel).
    """
    animationName: str
    elapsedTime: float
    pseudoElement: str


class TransitionEvent(Event, Protocol):
    """
    Protocol for CSS transition events
    (transitionstart, transitionend, transitionrun, transitioncancel).
    """
    propertyName: str
    elapsedTime: float
    pseudoElement: str


# ============================================================================
# Clipboard Events
# ============================================================================

class ClipboardEvent(Event, Protocol):
    """
    Protocol for clipboard manipulation events (copy, cut, paste).
    """
    clipboardData: Optional[DataTransfer]


# ============================================================================
# Navigation & History Events
# ============================================================================

class PopStateEvent(Event, Protocol):
    """
    Protocol for browser history navigation (popstate).
    Triggered when the user presses the browser's Back/Forward button.
    """
    state: object      # the state stored via pushState()


class HashChangeEvent(Event, Protocol):
    """
    Protocol for URL fragment / hash change events (hashchange).
    """
    oldURL: str
    newURL: str


class PageTransitionEvent(Event, Protocol):
    """
    Protocol for page transition events (pageshow, pagehide).
    """
    persisted: bool


class BeforeUnloadEvent(Event, Protocol):
    """
    Protocol for the event fired before a document is unloaded (beforeunload).
    Used to display a leave-page confirmation.
    """
    returnValue: str


# ============================================================================
# Error & Promise Events
# ============================================================================

class ErrorEvent(Event, Protocol):
    """
    Protocol for errors during script execution or resource loading (error).
    """
    message: str
    filename: str
    lineno: int
    colno: int
    error: Any


class PromiseRejectionEvent(Event, Protocol):
    """
    Protocol for unhandled promise rejections
    (unhandledrejection, rejectionhandled).
    """
    promise: Any
    reason: Any


# ============================================================================
# Custom & Media Events
# ============================================================================

class CustomEvent(Event, Protocol):
    """
    Protocol for developer-defined custom events.
    Created via the constructor new CustomEvent("name", { detail: ... }).
    """
    detail: Any


class MediaQueryListEvent(Event, Protocol):
    """
    Protocol for changes to a CSS media query evaluation (change on MediaQueryList).
    """
    media: str
    matches: bool


# ============================================================================
# Storage & Message Events
# ============================================================================

class StorageEvent(Event, Protocol):
    """
    Protocol for web storage change events (storage).
    Triggered when localStorage or sessionStorage is changed from another tab/window.
    """
    key: Optional[str]
    oldValue: Optional[str]
    newValue: Optional[str]
    url: str
    storageArea: Any


class MessageEvent(Event, Protocol):
    """
    Protocol for receiving cross-context messages
    (message — used by postMessage, WebSockets, SSE, BroadcastChannel).
    """
    data: Any
    origin: str
    lastEventId: str
    source: Any
    ports: Any


# ============================================================================
# Security & Progress Events
# ============================================================================

class SecurityPolicyViolationEvent(Event, Protocol):
    """
    Protocol for Content Security Policy (CSP) violations
    (securitypolicyviolation).
    """
    documentURI: str
    referrer: str
    blockedURI: str
    violatedDirective: str
    effectiveDirective: str
    originalPolicy: str
    disposition: str
    sourceFile: str
    statusCode: int
    lineNumber: int
    columnNumber: int
    sample: str


class ProgressEvent(Event, Protocol):
    """
    Protocol for measuring the progress of an ongoing process
    (progress, load, loadstart, loadend, abort, error, timeout — on XMLHttpRequest/Fetch).
    """
    lengthComputable: bool
    loaded: int
    total: int


# ============================================================================
# Device Events
# ============================================================================

class GamepadEvent(Event, Protocol):
    """
    Protocol for gamepad device interactions
    (gamepadconnected, gamepaddisconnected).
    """
    gamepad: Any


# ============================================================================
# Observer & Geometry Protocols (Not standard Event subclasses)
# ============================================================================

class DOMRectReadOnly(Protocol):
    """
    Protocol for information about an element's size and its position
    relative to the viewport.
    """
    x: float
    y: float
    width: float
    height: float
    top: float
    right: float
    bottom: float
    left: float


class ResizeObserverEvent(Protocol):
    """
    Protocol for an observer entry when an element is resized.
    Not a standard DOM event — used together with js.ResizeObserver.
    """
    contentRect: DOMRectReadOnly
    target: EventTarget


# ============================================================================
# Type Alias for Event Handlers
# ============================================================================

# EventHandler: type for event callbacks (on_click, on_input, etc.).
# Stored inside Props and bound to the DOM by pyodide_impl.py.
EventHandler: TypeAlias = Union[Callable[..., Any], Coroutine[Any, Any, Any]]
