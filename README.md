# PyOn-Py

**Python VDOM Framework on Pyodide & WebAssembly**

Build reactive web applications entirely in Python — no JavaScript required. PyOn-Py compiles your Python components into a Virtual DOM that runs natively in the browser via [Pyodide](https://pyodide.org/).

---

## Table of Contents

- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [Component API](#component-api)
  - [Creating a Component](#creating-a-component)
  - [Props & State](#props--state)
  - [Rendering](#rendering)
  - [Lifecycle Hooks](#lifecycle-hooks)
  - [Error Boundaries](#error-boundaries)
  - [Context (Provide / Inject)](#context-provide--inject)
  - [Refs](#refs)
- [Virtual DOM & `h()` Function](#virtual-dom--h-function)
- [Template Syntax](#template-syntax)
  - [Interpolation](#interpolation)
  - [Loops](#loops)
  - [Conditionals](#conditionals)
  - [Event Handlers in Templates](#event-handlers-in-templates)
  - [Child Components in Templates](#child-components-in-templates)
- [CSS Scoping](#css-scoping)
- [App & Application Lifecycle](#app--application-lifecycle)
- [Global State Management (Store)](#global-state-management-store)
- [Event Bus (EventEmitter)](#event-bus-eventemitter)
- [Router (SPA Navigation)](#router-spa-navigation)
- [DOM Event Types](#dom-event-types)
- [Static Typing Guide](#static-typing-guide)
- [Project Configuration (`pyon.toml`)](#project-configuration-pyontoml)
- [Architecture Overview](#architecture-overview)

---

## Quick Start

```bash
# Install pyon-py
pip install pyon-py

# Create a new project
mkdir my-app && cd my-app
pyon init

# Start development server
pyon dev
```

Open `http://localhost:8000` in your browser.

---

## CLI Reference

PyOn-Py ships with a CLI powered by [Click](https://click.palletsprojects.com/).

### `pyon init`

Initializes a new project with a minimal starter template.

```bash
pyon init
```

**Generated structure:**
```
my-app/
├── pyon.toml              # Project configuration
├── .gitignore
├── index.html             # Entry HTML with mount point
├── app.py                 # Application entrypoint
└── src/
    ├── App.py             # Root component
    ├── static/
    │   └── style.css      # Global styles
    ├── pages/
    │   └── Index.py       # Starter page component
    └── components/
        └── Card.py        # Starter reusable component
```

### `pyon dev`

Starts a local development server with hot-reload via Server-Sent Events (SSE).

```bash
pyon dev
```

- Serves files on `http://localhost:8000`
- Watches `.py` files and triggers automatic browser reload on changes
- Dynamically generates `/loader.js` with module dependency resolution
- Reads `.env` files and exposes `PYON_`-prefixed variables to the browser

### `pyon add <packages...>`

Installs packages and registers them in `pyon.toml` with WASM compatibility validation.

```bash
# Add a runtime dependency (validated for browser/WASM)
pyon add requests

# Add a dev-only dependency (local only, not bundled to browser)
pyon add --dev pytest
```

**Validation pipeline:**
1. Checks if the package is built into Pyodide (`BUILTIN`)
2. Verifies pure-Python wheel availability (`PURE_PYTHON`)
3. Warns on packages with C extensions (`INCOMPATIBLE`)
4. Caches validated `.whl` files in `packages_cache/`
5. Generates `pyon.lock` with resolved versions

### `pyon remove <packages...>`

Uninstalls packages and cleans up `pyon.toml`, caches, and lock files.

```bash
pyon remove requests
```

### `pyon download`

Pre-downloads browser-side assets for offline development.

```bash
pyon download
```

By default, this command downloads the Python wheels (packages) specified in `pyon.toml`.
If you want to download the entire Pyodide runtime for full offline use, set `local_pyodide = true` in the `[dev]` section of your `pyon.toml` file before running the command.

---

## Component API

### Creating a Component

Every UI element is a class that inherits from `Component`. Initialize state in `setup()`, define UI in `render()`.

```python
from pyon.core import Component, h


class Counter(Component):
    def setup(self):
        self._state = {"count": 0}

    def increment(self):
        self.set_state({"count": self._state["count"] + 1})

    def render(self):
        return h("button", {"on_click": self.increment}, [
            f"Clicked {self._state['count']} times"
        ])
```

> [!IMPORTANT]
> **Do not override `__init__`**. Use `setup()` instead. Overriding `__init__` triggers a deprecation warning and may break framework internals.

### Props & State

| Concept | Attribute | Description |
|---------|-----------|-------------|
| **Props** | `self.props` | Immutable data passed from the parent. Access via `self.props["key"]` or `self.props.get("key", default)`. |
| **State** | `self._state` | Mutable internal state. Always update via `self.set_state({...})` to trigger re-rendering. |

```python
class Greeting(Component):
    def setup(self):
        self._state = {"excited": False}

    def render(self):
        name = self.props.get("name", "World")
        suffix = "!" if self._state["excited"] else "."
        return h("span", {}, [f"Hello, {name}{suffix}"])
```

**Using the component:**
```python
h(Greeting, {"key": "greet", "name": "Alice"})
```

#### `set_state(updates)`

Merges `updates` into `self._state` and schedules a re-render. Multiple `set_state` calls within the same synchronous block are **batched** into a single render cycle via microtask scheduling.

```python
def handle_response(self, data):
    # These two calls are batched into ONE re-render
    self.set_state({"loading": False})
    self.set_state({"data": data})
```

### Rendering

The `render()` method must return either a **VNode** (via `h()`) or an **HTML template string**.

```python
# Option 1: VNode (programmatic)
def render(self):
    return h("div", {"class": "card"}, [
        h("h2", {}, [self.props["title"]]),
        h("p", {}, [self._state["content"]]),
    ])

# Option 2: Template string (declarative)
def render(self):
    return """
    <div class="card">
        <h2>{{ self.props["title"] }}</h2>
        <p>{{ self._state["content"] }}</p>
    </div>
    """
```

### Lifecycle Hooks

| Hook | When Called | Async Support |
|------|------------|---------------|
| `setup()` | Once, immediately after instantiation. Use for state init. | No |
| `on_mount()` | Once, after the component is mounted to the DOM. | Yes (`async def`) |
| `on_update(prev_props, prev_state)` | After every state/prop change and DOM patch. | Yes (`async def`) |
| `on_unmount()` | When the component is removed from the DOM tree. | Yes (`async def`) |

```python
class DataFetcher(Component):
    def setup(self):
        self._state = {"data": None, "loading": True}

    async def on_mount(self):
        response = await fetch("/api/data")
        data = await response.json()
        self.set_state({"data": data, "loading": False})

    def on_update(self, prev_props, prev_state):
        if prev_props.get("query") != self.props.get("query"):
            self.set_state({"loading": True})

    def on_unmount(self):
        print("Cleaned up!")
```

### Error Boundaries

Override `component_did_catch(error)` to catch rendering errors from any descendant component, preventing the entire app from crashing.

```python
class ErrorBoundary(Component):
    def setup(self):
        self._state = {"error": None}

    def component_did_catch(self, error):
        self.set_state({"error": str(error)})

    def render(self):
        if self._state["error"]:
            return h("div", {"class": "error"}, [
                f"Something went wrong: {self._state['error']}"
            ])
        return h("div", {}, self.props.get("children", []))
```

### Context (Provide / Inject)

Share data across component trees without prop drilling.

```python
# Provider (ancestor)
class ThemeProvider(Component):
    def setup(self):
        self.provide("theme", "dark")

    def render(self):
        return h("div", {}, self.props.get("children", []))

# Consumer (any descendant)
class ThemedButton(Component):
    def setup(self):
        self.theme = self.inject("theme", "light")  # "dark"

    def render(self):
        return h("button", {"class": self.theme}, ["Click"])
```

Context can also be provided at the application level via `app.provide()` (see [App](#app--application-lifecycle)).

### Refs

Access real DOM elements via the `refs` dictionary.

```python
class InputFocus(Component):
    def setup(self):
        self._state = {}

    async def on_mount(self):
        self.refs["input"].focus()

    def render(self):
        return h("input", {"ref": "input", "type": "text"})
```

---

## Virtual DOM & `h()` Function

The `h()` function creates VNode objects — the building blocks of the virtual DOM tree.

```python
h(tag, props?, children?) -> VNode
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `tag` | `str \| type` | HTML tag name (`"div"`, `"button"`) or a Component class (`Card`) |
| `props` | `dict` | Attributes, event handlers, and component props |
| `children` | `list` | Child VNodes, strings, integers, or floats |

**Examples:**
```python
# HTML element
h("div", {"class": "container", "id": "main"}, ["Hello World"])

# Event handler
h("button", {"on_click": self.handle_click}, ["Submit"])

# Nested structure
h("ul", {}, [
    h("li", {"key": "1"}, ["Item 1"]),
    h("li", {"key": "2"}, ["Item 2"]),
])

# Component as tag
h(Card, {"key": "card-1", "title": "My Card"}, [
    h("p", {}, ["Card body content"])  # Accessible via props["children"]
])
```

> [!TIP]
> Always provide a `key` prop for components and list items to enable efficient keyed reconciliation during re-rendering.

---

## Template Syntax

Components can return HTML template strings from `render()` instead of using `h()`. Templates are parsed into an AST once and cached per class — subsequent re-renders only re-evaluate expressions.

### Interpolation

Use `{{ expression }}` to embed Python expressions:

```python
def render(self):
    return """
    <div>
        <h1>{{ self.props.get("title", "Default") }}</h1>
        <p>Count: {{ self._state["count"] }}</p>
        <span>{{ "Active" if self._state["active"] else "Inactive" }}</span>
    </div>
    """
```

### Loops

Use `{% for ... in ... %}` and `{% endfor %}`:

```python
def render(self):
    return """
    <ul>
        {% for item in self._state["items"] %}
            <li key="{{ item['id'] }}">{{ item["name"] }}</li>
        {% endfor %}
    </ul>
    """
```

### Conditionals

Use `{% if %}`, `{% elif %}`, `{% else %}`, and `{% endif %}`:

```python
def render(self):
    return """
    <div>
        {% if self._state["loading"] %}
            <p>Loading...</p>
        {% elif self._state["error"] %}
            <p class="error">{{ self._state["error"] }}</p>
        {% else %}
            <p>{{ self._state["data"] }}</p>
        {% endif %}
    </div>
    """
```

### Event Handlers in Templates

Wrap handler expressions in double quotes **and** double curly braces:

```python
def render(self):
    return """
    <button on_click="{{ lambda e: self.increment() }}">Click me</button>
    <button on_click="{{ self.reset }}">Reset</button>
    """
```

### Child Components in Templates

Capitalized tags are resolved as Component classes from the module's scope:

```python
from src.components.Card import Card

class Page(Component):
    def render(self):
        return """
        <div>
            <Card title="Hello" key="card-1">
                <p>Slot content here</p>
            </Card>
        </div>
        """
```

> [!NOTE]
> The component class (`Card`) must be imported in the same module where the template is defined.

---

## CSS Scoping

PyOn-Py provides Vue-style hash-based CSS scoping. Styles defined on a component are automatically isolated so they never leak to other components.

```python
class Card(Component):
    styles = """
    .card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 1rem;
    }
    .card:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    @media (max-width: 600px) {
        .card { padding: 0.5rem; }
    }
    """

    def render(self):
        return h("div", {"class": "card"}, [
            h("h2", {}, [self.props["title"]])
        ])
```

**How it works:**
1. `__init_subclass__` computes an MD5 hash from the fully qualified class name → e.g. `v-a1b2c3d`
2. CSS selectors are automatically rewritten: `.card` → `.card[data-v-a1b2c3d]`
3. The `data-v-a1b2c3d` attribute is injected into all HTML VNodes rendered by that component
4. `@media` queries and `@keyframes` are preserved correctly

---

## App & Application Lifecycle

### Creating an App

```python
from pyon.core import create_app
from src.App import App as RootComponent

app = create_app(RootComponent)
app.mount("#app")
```

### `App` Methods

| Method | Description |
|--------|-------------|
| `mount(selector="#app")` | Expands the component tree, injects scoped CSS, and performs initial DOM render. |
| `provide(key, value)` | Registers a global context value accessible by any component via `self.inject(key)`. |

### Global Context

```python
app = create_app(RootComponent)
app.provide("api_base", "https://api.example.com")
app.provide("theme", "dark")
app.mount("#app")
```

Any component in the tree can access these values:
```python
class MyComponent(Component):
    def setup(self):
        self.api_base = self.inject("api_base")
```

### Teardown

```python
from pyon.core import teardown

teardown()  # Unmounts all components, cleans up router, clears all state
```

---

## Global State Management (Store)

The `Store` class provides Pinia/Zustand-style reactive global state. Assigning any public attribute automatically triggers subscriber notifications.

### Defining a Store

```python
from pyon.store import Store


class UserStore(Store):
    username: str = "Guest"
    is_authenticated: bool = False
    cart_items: list = []

    def login(self, username: str):
        self.username = username          # Auto-triggers notify()
        self.is_authenticated = True      # Auto-triggers notify()

    def add_to_cart(self, item: str):
        self.cart_items.append(item)
        self.notify()  # Manual notify for in-place mutations


user_store = UserStore()
```

### Using a Store in Components

```python
class UserProfile(Component):
    def setup(self):
        self.use_store(user_store)  # Auto-subscribes, auto-unsubscribes on unmount

    def render(self):
        if user_store.is_authenticated:
            return h("p", {}, [f"Welcome, {user_store.username}!"])
        return h("p", {}, ["Please log in."])
```

> [!IMPORTANT]
> Always call `store.notify()` manually when mutating a collection in-place (e.g. `.append()`, `.pop()`, `dict[key] = value`). Direct attribute assignment (e.g. `store.items = new_list`) triggers notification automatically.

---

## Event Bus (EventEmitter)

A generic Pub-Sub system for decoupled cross-component communication — ideal for plugins, WebSocket bridges, and global notifications.

### Creating an Event Bus

```python
from pyon.core.bus import EventEmitter

global_bus = EventEmitter()
```

### API

| Method | Description |
|--------|-------------|
| `on(event, listener) -> off_fn` | Subscribe to an event. Returns an unsubscribe function. |
| `off(event, listener)` | Manually unsubscribe a listener. |
| `emit(event, *args, **kwargs)` | Emit an event with payload arguments. |

### Using in Components

```python
class NotificationBar(Component):
    def setup(self):
        self._state = {"message": ""}
        self.use_event(global_bus, "SHOW_TOAST", self.show_toast)

    def show_toast(self, message: str):
        self.set_state({"message": message})

    def render(self):
        return h("div", {"class": "toast"}, [self._state["message"]])
```

```python
# Anywhere in the app:
global_bus.emit("SHOW_TOAST", "Item saved successfully!")
```

> [!TIP]
> Use `self.use_event(bus, event, listener)` instead of `bus.on(event, listener)` inside components — it automatically unsubscribes on unmount, preventing memory leaks.

---

## Router (SPA Navigation)

PyOn-Py includes a client-side SPA router integrated with browser history.

### Setup

```python
from pyon.core import create_app
from pyon.router import Router, RouterView, Link, RouteDef

routes: list[RouteDef] = [
    {"path": "/", "component": HomePage, "key": "home"},
    {"path": "/users/:id", "component": UserPage, "key": "user"},
    {"path": "*", "component": NotFoundPage, "key": "404"},
]

router = Router(routes)

app = create_app(RootComponent)
app.provide("router", router)
app.mount("#app")
```

### `RouterView`

Renders the component matching the current URL path. Place it in your root component:

```python
class RootComponent(Component):
    def render(self):
        return h("div", {}, [
            h("nav", {}, [
                h(Link, {"key": "home-link", "to": "/"}, ["Home"]),
                h(Link, {"key": "about-link", "to": "/about"}, ["About"]),
            ]),
            h(RouterView, {"key": "router-view"}),
        ])
```

### `Link`

Client-side navigation link that prevents full page reloads:

```python
h(Link, {"to": "/users/42"}, ["View User 42"])
```

- Renders an `<a>` element with SPA navigation
- Automatically adds `"active"` CSS class when the link matches the current route

### Dynamic Route Parameters

Routes with `:param` segments extract parameters passed as props:

```python
# Route: {"path": "/users/:id", "component": UserPage, "key": "user"}

class UserPage(Component):
    def setup(self):
        user_id = self.props.get("id")  # "42" from /users/42
```

### Programmatic Navigation

```python
class MyComponent(Component):
    def setup(self):
        self.router = self.inject("router")

    def go_home(self):
        self.router.push("/")        # push to history
        # self.router.replace("/")   # replace current entry

    def render(self):
        current = self.router.current_path   # e.g. "/users/42"
        query = self.router.query            # e.g. {"page": "2"}
        return h("div", {}, [current])
```

---

## DOM Event Types

PyOn-Py provides comprehensive type protocols in `pyon.core.events` for all standard DOM events. Use these for static type checking of event handlers.

```python
from pyon.core.events import MouseEvent, KeyboardEvent, InputEvent, Event

class Form(Component):
    def handle_click(self, e: MouseEvent):
        print(f"Clicked at ({e.clientX}, {e.clientY})")

    def handle_key(self, e: KeyboardEvent):
        if e.key == "Enter":
            self.submit()

    def handle_input(self, e: InputEvent):
        self.set_state({"value": e.target.value})
```

**Available event protocols:**

| Category | Types |
|----------|-------|
| **Mouse** | `MouseEvent`, `PointerEvent`, `WheelEvent`, `DragEvent` |
| **Keyboard** | `KeyboardEvent` |
| **Form** | `InputEvent`, `ChangeEvent`, `SubmitEvent`, `FormDataEvent`, `CompositionEvent` |
| **Focus** | `FocusEvent` |
| **Touch** | `TouchEvent`, `Touch`, `TouchList` |
| **Animation** | `AnimationEvent`, `TransitionEvent` |
| **Clipboard** | `ClipboardEvent` |
| **Browser** | `PopStateEvent`, `HashChangeEvent`, `PageTransitionEvent`, `BeforeUnloadEvent` |
| **Error** | `ErrorEvent`, `PromiseRejectionEvent` |
| **Media** | `MediaQueryListEvent` |
| **Storage** | `StorageEvent` |
| **Messaging** | `MessageEvent` |
| **Misc** | `CustomEvent`, `ProgressEvent`, `GamepadEvent`, `ResizeObserverEvent` |

---

## Static Typing Guide

PyOn-Py is designed with first-class static typing support via Python's `Generic` system.

### Typed Props

Define a `TypedDict` for your component's props:

```python
from pyon.core import Component, BaseProps, h


class CardProps(BaseProps):
    title: str
    subtitle: str


class Card(Component[CardProps]):
    def render(self):
        # self.props is typed as CardProps
        # IDE autocomplete works for self.props["title"]
        return h("div", {}, [
            h("h2", {}, [self.props["title"]]),
            h("p", {}, [self.props["subtitle"]]),
        ])
```

### Typed State

Define a state TypedDict and pass it as the second generic parameter:

```python
from typing import TypedDict


class CounterState(TypedDict):
    count: int
    loading: bool


class Counter(Component[BaseProps, CounterState]):
    def setup(self):
        self._state: CounterState = {"count": 0, "loading": False}

    def increment(self):
        # self._state is typed as CounterState
        self.set_state({"count": self._state["count"] + 1})
```

### Typed Event Handlers

Use event protocols from `pyon.core.events`:

```python
from pyon.core.events import MouseEvent, KeyboardEvent


class Interactive(Component):
    def handle_click(self, e: MouseEvent) -> None:
        print(e.clientX, e.clientY)  # Fully typed

    def handle_keydown(self, e: KeyboardEvent) -> None:
        if e.key == "Escape":
            self.close()
```

### Typed Store

```python
from pyon.store import Store


class AppStore(Store):
    theme: str = "light"
    language: str = "en"
    notifications: list[str] = []

    def toggle_theme(self) -> None:
        self.theme = "dark" if self.theme == "light" else "light"
```

---

## Project Configuration (`pyon.toml`)

```toml
[project]
name = "my-pyon-app"
version = "0.1.0"

[dependencies]
# Runtime packages (validated for WASM/browser compatibility)
packages = [
    "requests>=2.31.0",
]

[dev-dependencies]
# Development-only packages (local only, not bundled to browser)
packages = [
    "pytest>=7.0.0",
]

[dev]
# Pyodide version to use
pyodide_version = "314.0.6"

# Distribution type: "core" or "full"
pyodide_release = "core"

# Set to true when Pyodide assets are cached locally (set by `pyon download`)
local_pyodide = false
```

---

## Tailwind CSS Integration

PyOn-Py templates output standard HTML `class` attributes, making it fully compatible with the official Tailwind CSS CLI. Furthermore, PyOn-Py's dev server provides zero-refresh **CSS Hot-Reloading**.

### 1. Initialize Tailwind
In your PyOn-Py project directory, install and initialize Tailwind:
```bash
npm install tailwindcss @tailwindcss/cli
```

### 2. Configure `tailwind.config.js`
Instruct Tailwind to scan your Python component files:
```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.py", "./index.html"],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

### 3. Setup CSS & HTML
Create an `input.css` with the Tailwind directives:
```css
@import "tailwindcss";
```
Link the output file in your `index.html`:
```html
<link rel="stylesheet" href="/src/static/output.css">
```

### 4. Run Watchers
Run both the Tailwind CLI and PyOn-Py dev server concurrently in two terminal tabs:
```bash
# Terminal 1: Watch Python files & render CSS
npx tailwindcss -i ./input.css -o ./src/static/output.css --watch

# Terminal 2: Run PyOn-Py Server
pyon dev
```

Whenever you modify Tailwind classes inside your Python components, the CSS will be compiled and injected into the browser **instantly (~0ms)** without reloading Pyodide or resetting your application state!

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Application                         │
│  app.py ──► create_app(Root) ──► app.mount("#app")              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                     Framework Core (pyon/core/)                 │
│                                                                 │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────────┐    │
│  │   App    │  │ Component │  │  VNode   │  │   Differ     │    │
│  │ mount()  │  │ render()  │  │   h()    │  │   diff()     │    │
│  │ provide()│  │ setup()   │  │          │  │   patches    │    │
│  │ flush()  │  │ set_state │  │          │  │              │    │
│  └────┬─────┘  └─────┬─────┘  └──────────┘  └───────┬──────┘    │
│       │              │                              │           │
│  ┌────▼──────────────▼──────────────────────────────▼───────┐   │
│  │                    _expand_tree()                        │   │
│  │  Component class → instantiate → setup → _render → VNode │   │
│  │  + Context propagation + CSS scope + Error boundaries    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐     │
│  │ Template │  │   CSS    │  │  Store   │  │  EventBus    │     │
│  │ Compiler │  │ Scoping  │  │ (Global) │  │ (Pub-Sub)    │     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘     │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      Router                              │   │
│  │  Router · RouterView · Link · Dynamic Params · Query     │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                   Pyodide Bridge (pyon/bridge/)                 │
│  full_render() · apply_patches() · inject_scoped_css()          │
│  JS Proxy management · Event delegation · DOM operations        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    Browser (WebAssembly)                        │
│  Pyodide runtime · Real DOM · CSS · Browser APIs                │
└─────────────────────────────────────────────────────────────────┘
```

**Update cycle:**
1. `set_state()` / `store.attr = value` / `bus.emit()` → triggers update
2. Microtask batching coalesces multiple state changes into one render
3. `_expand_tree()` re-renders the affected subtree
4. `diff()` computes minimal patches (`CREATE`, `REMOVE`, `REPLACE`, `UPDATE_PROPS`, `SET_TEXT`, `REORDER_CHILDREN`)
5. `apply_patches()` applies DOM mutations via Pyodide bridge
6. Lifecycle hooks (`on_update`, `on_mount`, `on_unmount`) are dispatched

---

## License

MIT