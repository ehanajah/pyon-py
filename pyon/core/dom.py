from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any, Protocol, overload


class NodeList(Protocol):
    """Protocol for the NodeList object that stores a collection of DOM nodes."""
    length: int
    
    def __len__(self) -> int: ...
    @overload
    def __getitem__(self, index: int) -> DOMElement | DOMTextNode: ...
    @overload
    def __getitem__(self, index: slice) -> list[DOMElement | DOMTextNode]: ...
    def item(self, index: int) -> DOMElement | DOMTextNode | None: ...
    def forEach(self, callback: Callable[[DOMElement | DOMTextNode, int, NodeList], Any]) -> None: ...
    def __iter__(self) -> Iterator[DOMElement | DOMTextNode]: ...


class DOMTokenList(Protocol):
    """Protocol for the classList attribute (DOMTokenList)."""
    length: int
    value: str
    
    def add(self, *tokens: str) -> None: ...
    def remove(self, *tokens: str) -> None: ...
    def toggle(self, token: str, force: bool | None = None) -> bool: ...
    def contains(self, token: str) -> bool: ...
    def replace(self, oldToken: str, newToken: str) -> bool: ...
    def item(self, index: int) -> str | None: ...


class CSSStyleDeclaration(Protocol):
    """Protocol for an inline CSS style declaration."""
    cssText: str
    length: int
    
    # Common CSS properties
    display: str
    position: str
    width: str
    height: str
    margin: str
    padding: str
    color: str
    backgroundColor: str
    fontSize: str
    fontWeight: str
    border: str
    opacity: str
    visibility: str
    overflow: str
    zIndex: str
    transform: str
    transition: str
    animation: str
    cursor: str
    pointerEvents: str
    boxSizing: str
    flexDirection: str
    justifyContent: str
    alignItems: str
    gap: str
    gridTemplateColumns: str
    gridTemplateRows: str
    top: str
    right: str
    bottom: str
    left: str
    maxWidth: str
    maxHeight: str
    minWidth: str
    minHeight: str
    textAlign: str
    textDecoration: str
    lineHeight: str
    letterSpacing: str
    whiteSpace: str
    wordBreak: str
    borderRadius: str
    boxShadow: str
    outline: str
    background: str
    backgroundImage: str
    backgroundSize: str
    backgroundPosition: str
    backgroundRepeat: str
    flex: str
    flexWrap: str
    flexGrow: str
    flexShrink: str
    flexBasis: str
    order: str
    alignSelf: str
    justifySelf: str
    float_: str       # Maps to CSS 'float' (Python reserved word)
    clear: str
    objectFit: str
    objectPosition: str
    userSelect: str
    resize: str
    appearance: str
    filter_: str      # Maps to CSS 'filter' (Python reserved word)
    willChange: str
    contain: str
    aspectRatio: str
    inset: str
    
    def getPropertyValue(self, property: str) -> str: ...
    def setProperty(self, propertyName: str, value: str | None, priority: str = "") -> None: ...
    def removeProperty(self, property: str) -> str: ...
    def item(self, index: int) -> str: ...


class DOMRect(Protocol):
    """Protocol for the size and position of an element returned by getBoundingClientRect."""
    x: float
    y: float
    width: float
    height: float
    top: float
    right: float
    bottom: float
    left: float


class DOMTextNode(Protocol):
    """Base protocol for a DOM Text Node."""
    textContent: str
    childNodes: NodeList
    def remove(self) -> None: ...


class DOMElement(DOMTextNode, Protocol):
    """Base protocol for a DOM Element (HTML/SVG).
    Contains the method and property signatures to be fulfilled
    by any engine (Pyodide, Native WASM, or Mock).
    """
    
    # -- Node properties --
    nodeName: str
    nodeType: int
    nodeValue: str | None
    parentNode: DOMElement | DOMTextNode | None
    parentElement: DOMElement | None
    firstChild: DOMElement | DOMTextNode | None
    lastChild: DOMElement | DOMTextNode | None
    nextSibling: DOMElement | DOMTextNode | None
    previousSibling: DOMElement | DOMTextNode | None
    ownerDocument: Any
    childNodes: NodeList
    
    # -- Element properties --
    id: str
    tagName: str
    className: str
    classList: DOMTokenList
    dataset: Any
    children: NodeList
    innerHTML: str
    outerHTML: str
    innerText: str
    value: str
    
    # Scroll properties
    scrollTop: float
    scrollLeft: float
    scrollWidth: float
    scrollHeight: float
    
    # Client properties
    clientWidth: float
    clientHeight: float
    clientTop: float
    clientLeft: float
    
    # Offset properties
    offsetWidth: float
    offsetHeight: float
    offsetTop: float
    offsetLeft: float
    offsetParent: DOMElement | None
    
    # Global HTMLElement properties
    hidden: bool
    tabIndex: int
    title: str
    dir: str
    lang: str
    draggable: bool
    slot: str
    contentEditable: str
    style: CSSStyleDeclaration
    
    # -- Element methods --
    def setAttribute(self, name: str, value: str) -> None: ...
    def getAttribute(self, name: str) -> str | None: ...
    def removeAttribute(self, name: str) -> None: ...
    def hasAttribute(self, name: str) -> bool: ...
    def toggleAttribute(self, name: str, force: bool | None = None) -> bool: ...
    
    def closest(self, selectors: str) -> DOMElement | None: ...
    def matches(self, selectors: str) -> bool: ...
    
    def querySelector(self, selectors: str) -> DOMElement | None: ...
    def querySelectorAll(self, selectors: str) -> NodeList: ...
    def getElementsByClassName(self, names: str) -> NodeList: ...
    def getElementsByTagName(self, name: str) -> NodeList: ...
    
    def appendChild(self, child: DOMElement | DOMTextNode) -> DOMElement | DOMTextNode: ...
    def removeChild(self, child: DOMElement | DOMTextNode) -> DOMElement | DOMTextNode: ...
    def replaceWith(self, *nodes: DOMElement | DOMTextNode | str) -> None: ...
    def insertBefore(self, new_el: DOMElement | DOMTextNode, reference: DOMElement | DOMTextNode | None) -> DOMElement | DOMTextNode: ...
    
    def cloneNode(self, deep: bool = False) -> DOMElement | DOMTextNode: ...
    def contains(self, other: DOMElement | DOMTextNode | None) -> bool: ...
    def compareDocumentPosition(self, other: DOMElement | DOMTextNode) -> int: ...
    
    def getBoundingClientRect(self) -> DOMRect: ...
    def getClientRects(self) -> Iterable[DOMRect]: ...
    
    def scroll(self, x: float, y: float) -> None: ...
    def scrollTo(self, x: float, y: float) -> None: ...
    def scrollBy(self, x: float, y: float) -> None: ...
    def scrollIntoView(self, arg: bool | Any = True) -> None: ...
    
    def focus(self, options: Any = None) -> None: ...
    def blur(self) -> None: ...
    def click(self) -> None: ...
    def animate(self, keyframes: Any, options: Any) -> Any: ...
    
    # Event listeners
    def addEventListener(self, event: str, callback: Any, options: Any = None) -> None: ...
    def removeEventListener(self, event: str, callback: Any, options: Any = None) -> None: ...
    def dispatchEvent(self, event: Any) -> bool: ...
    
    # Node methods
    def normalize(self) -> None: ...
    def isEqualNode(self, otherNode: DOMElement | DOMTextNode | None) -> bool: ...
    def isSameNode(self, otherNode: DOMElement | DOMTextNode | None) -> bool: ...
    def hasChildNodes(self) -> bool: ...
    def replaceChild(self, newChild: DOMElement | DOMTextNode, oldChild: DOMElement | DOMTextNode) -> DOMElement | DOMTextNode: ...
    
    # Removal & insertion from the tree
    def remove(self) -> None: ...
    def before(self, *nodes: DOMElement | DOMTextNode | str) -> None: ...
    def after(self, *nodes: DOMElement | DOMTextNode | str) -> None: ...
    def prepend(self, *nodes: DOMElement | DOMTextNode | str) -> None: ...
    def append(self, *nodes: DOMElement | DOMTextNode | str) -> None: ...
    def replaceChildren(self, *nodes: DOMElement | DOMTextNode | str) -> None: ...
