# Spesifikasi Desain SPA Router Pyon-Py

Dokumen ini mendeskripsikan arsitektur dan implementasi dari modul **SPA Router** untuk framework Pyon-Py. Router ini dirancang khusus mengikuti kapabilitas ekosistem Pyon, mencakup injeksi konteks (*Dependency Injection*), siklus hidup komponen, dan proksi *JavaScript* via Pyodide.

## 1. Struktur Modul

Modul router akan ditempatkan pada `pyon/router/` dan memiliki pemisahan tanggung jawab sebagai berikut:

```text
pyon/router/
├── __init__.py       (Public API Exports: Router, RouterView, Link)
├── core.py           (Kelas inti Router: State URL & Sinkronisasi browser)
└── components.py     (Komponen UI reaktif: RouterView & Link)
```

## 2. Kelas Inti: `Router` (Logika Sejarah Browser)
Kelas ini bertugas sebagai penghubung antara API `window.history` dari browser dengan antarmuka Pyon.

**Fitur Kunci:**
- **URL Tracking:** Melacak dan menyimpan status *path* saat ini.
- **Event Proxying:** Membungkus penanganan `popstate` browser menggunakan `ffi.create_proxy()` milik Pyodide.
- **Push/Replace API:** Menyediakan antarmuka untuk program mengubah rute.
- **Pub/Sub System:** Memberi tahu komponen UI jika rute berganti (pola *Observer*).

**Desain Awal:**
```python
from typing import Callable, TypedDict, Any
from pyon.browser import window, ffi

class RouteDef(TypedDict):
    path: str
    component: type

class Router:
    def __init__(self, routes: list[RouteDef]):
        self.routes = routes
        self.current_path = window.location.pathname
        self._subscribers: list[Callable[[str], None]] = []

        # Ikat event popstate menggunakan proxy (wajib untuk Pyodide)
        self._proxy = ffi.create_proxy(self._on_popstate)
        window.addEventListener("popstate", self._proxy)

    def _on_popstate(self, event: Any) -> None:
        self.current_path = window.location.pathname
        self._notify()

    def push(self, path: str) -> None:
        if self.current_path == path:
            return
        window.history.pushState(None, "", path)
        self.current_path = path
        self._notify()

    def replace(self, path: str) -> None:
        if self.current_path == path:
            return
        window.history.replaceState(None, "", path)
        self.current_path = path
        self._notify()

    def _notify(self) -> None:
        for callback in self._subscribers:
            callback(self.current_path)
            
    def subscribe(self, callback: Callable[[str], None]) -> None:
        self._subscribers.append(callback)
        
    def unsubscribe(self, callback: Callable[[str], None]) -> None:
        self._subscribers.remove(callback)
        
    def destroy(self) -> None:
        """Pembersihan proxy untuk mencegah memory leak"""
        window.removeEventListener("popstate", self._proxy)
        self._proxy.destroy()
```

## 3. Komponen `<RouterView>`
Tugas `RouterView` adalah berlangganan ke *state* rute dari `Router`, dan merender komponen yang cocok dengan URL saat ini. `Router` diambil menggunakan sistem **Context** (`self.inject("router")`).

**Desain Awal:**
```python
from pyon.core import Component, h

class RouterView(Component):
    def __init__(self, props):
        super().__init__(props)
        self.router = self.inject("router")
        self._state = {"path": self.router.current_path}
        
    def on_mount(self) -> None:
        self.router.subscribe(self._on_route_change)
        
    def on_unmount(self) -> None:
        self.router.unsubscribe(self._on_route_change)

    def _on_route_change(self, new_path: str) -> None:
        # Memicu render ulang saat path berubah
        self.set_state({"path": new_path})

    def render(self):
        current_path = self._state["path"]
        
        # Algoritma pencocokan URL
        for route in self.router.routes:
            if route["path"] == current_path:
                return h(route["component"], {})
                
        return h("div", {"class": "404-fallback"}, ["404 - Halaman Tidak Ditemukan"])
```

## 4. Komponen `<Link>`
Komponen untuk menavigasi tanpa perlu *full-page reload*. Komponen ini akan memblokir aksi bawaan `<a>` dan mengalihkannya ke metode `push()` pada Router.

**Desain Awal:**
```python
from pyon.core import Component, BaseProps, h

class LinkProps(BaseProps):
    to: str

class Link(Component[LinkProps]):
    def __init__(self, props):
        super().__init__(props)
        self.router = self.inject("router")
        
    def _handle_click(self, event) -> None:
        event.preventDefault()
        self.router.push(self.props["to"])
        
    def render(self):
        attrs = {k: v for k, v in self.props.items() if k not in ["to", "children", "key"]}
        
        return h("a", {
            "href": self.props["to"],
            "on_click": self._handle_click,
            **attrs
        }, self.props.get("children", []))
```

## 5. Implementasi & Pengikatan di Root Aplikasi
Pada berkas utama pengguna (`app.py`), pendaftaran *Router* ke dalam siklus aplikasi dijamin ringkas berkat Dependency Injection (Context).

```python
from pyon.core import create_app
from pyon.router import Router

# Inisialisasi daftar rute
router = Router([
    {"path": "/", "component": HomePage},
    {"path": "/about", "component": AboutPage},
])

def start():
    app = create_app(AppRootComponent)
    # Suntikkan router secara global
    app.provide("router", router)
    app.mount("#app")
```

## 6. Fitur Lanjutan (Telah Terimplementasi)
- **Dynamic Routing & Ekstraksi Prop:** URL berpola (`/users/:id`) secara otomatis diekstrak menjadi `props["id"]`.
- **Query Parameters:** String pencarian URL (`?search=keyword`) otomatis diekstrak menjadi `props["query"]["search"]`.
- **Wildcard / 404 Fallback:** Mendukung deklarasi rute `{"path": "*"}` untuk menangkap semua URL yang tidak valid.
- **Scroll Restoration:** Perpindahan halaman lewat `Router.push` atau `Router.replace` otomatis menggulirkan viewport ke bagian paling atas layar.
- **Global Active State:** Dapat diakses via `router.is_active(path)`, membuat komponen tautan reaktif bereaksi memancarkan kelas visual aktif.
