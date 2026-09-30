# Async Components & Lazy Loading Boundaries

> **Status**: Draft — Menunggu persetujuan  
> **Prioritas**: 4 (Eksplorasi Arsitektur Lanjutan)  
> **Referensi**: [ROADMAP.md](../ROADMAP.md), [FRAGMENT_RETURN.md](./FRAGMENT_RETURN.md)

---

## 1. Ringkasan Masalah

Saat ini **seluruh pohon komponen harus tersedia dan terekspansi secara sinkron** dalam satu pass `_expand_tree()`. Setiap `Component` class yang direferensikan di template atau `h()` harus sudah di-import sebelum render pertama.

Implikasi:
1. **Bundle monolitik** — Semua modul Python dimuat ke Pyodide sekaligus saat startup, meningkatkan _Time-to-Interactive_ (TTI).
2. **Tidak ada code-splitting** — Halaman yang jarang dikunjungi (misal: Settings, Admin) tetap dimuat di awal.
3. **`render()` tidak bisa menunggu** — Return type `VNode | str` bersifat sinkron mutlak. Tidak ada mekanisme bagi VDOM engine untuk "menunda" ekspansi sambil menampilkan UI placeholder.

---

## 2. Tujuan

Mengimplementasikan dua primitif baru:

| Primitif | Deskripsi |
|---|---|
| **`lazy(loader)`** | Factory function yang mengembalikan Component class pembungkus. Class ini menunda import modul asli hingga saat pertama kali di-render. |
| **`Suspense`** | Boundary component bawaan framework yang menangkap state "sedang memuat" dari komponen lazy turunannya, lalu menampilkan fallback UI hingga seluruh resolusi selesai. |

### Target API

```python
# pages/__init__.py
from pyon.core import lazy

LazyProfile = lazy("pages.Profile", "Profile")
LazySettings = lazy(lambda: custom_network_loader("Settings"))
```

```python
# App.py
from pyon.core import Component, Suspense
from pages import LazyProfile

class App(Component):
    def render(self):
        return """
        <Suspense fallback="<div class='spinner'>Memuat...</div>">
            <LazyProfile user_id="{{ self.props['user_id'] }}" />
        </Suspense>
        """
```

```python
# Router integration
from pyon.router import Router, lazy

router = Router(routes=[
    {"path": "/",        "component": Home,                          "key": "home"},
    {"path": "/profile", "component": lazy("pages.Profile", "Profile"), "key": "profile"},
    {"path": "/settings","component": lazy("pages.Settings","Settings"),"key": "settings"},
])
```

---

## 3. Analisis Arsitektur Terdampak

### 3.1 Constraint Fundamental

| Subsistem | Kondisi Saat Ini | Dampak |
|---|---|---|
| `Component._render()` | Sinkron (`render() → VNode \| str`) | `render()` **tidak bisa** `await`. Mekanisme async harus bekerja di luar siklus render. |
| `_expand_tree()` | DFS sinkron rekursif. Sudah memiliki pattern `ErrorCaughtByBoundary` untuk stack unwinding. | Pattern yang **sama persis** dapat digunakan untuk `SuspensePending` exception. |
| DOM Path (`"0.1.2"`) | 1-to-1 mapping ke DOM node | Placeholder/fallback **harus** menempati path yang sama dengan konten final. |
| `component_map[full_key]` | Cache instance berdasarkan hierarchical key | Instance lazy wrapper harus **stabil** di map agar orphan detection tidak salah hapus. |
| CSS Injection | Sekali jalan di `App.mount()` | Komponen lazy yang baru dimuat mendaftarkan CSS via `__init_subclass__`. `inject_scoped_css` **harus dipanggil ulang**. |
| `on_mount` lifecycle | Dipanggil **setelah** DOM dirender via `pending_mounts` | Lazy component yang baru ter-resolve harus melalui siklus mount yang sama. |

### 3.2 Preseden: Error Boundary Pattern

`_expand_tree()` sudah mengimplementasikan mekanisme stack unwinding via exception:

```
render() throws Error
  → catch Exception di _expand_tree
  → walk up parent_key chain → cari component_did_catch override
  → wrap dalam ErrorCaughtByBoundary(boundary_key, error)
  → re-raise hingga boundary level
  → boundary catches → render fallback UI
```

**Suspense menggunakan pola yang identik**, mengganti:
- `Exception` → `SuspensePending`
- `component_did_catch` override → `_is_suspense_boundary` class attribute
- `ErrorCaughtByBoundary` → `SuspenseCaughtByBoundary`

---

## 4. Desain Internal

### 4.1 Exception Baru

```python
class SuspensePending(Exception):
    """Dilempar oleh lazy component saat modul belum ter-resolve."""
    def __init__(self, lazy_class: type):
        self.lazy_class = lazy_class


class SuspenseCaughtByBoundary(Exception):
    """Membawa SuspensePending ke Suspense boundary terdekat."""
    def __init__(self, boundary_key: str, lazy_class: type):
        self.boundary_key = boundary_key
        self.lazy_class = lazy_class
```

### 4.2 `lazy()` Factory Function

`lazy()` mengembalikan sebuah **class** (bukan instance) yang merupakan subclass `Component`. Class ini memiliki state resolusi di level class (`ClassVar`), sehingga semua instance berbagi status loading yang sama.

```python
def lazy(
    loader: str | Callable[[], Coroutine[Any, Any, type[Component]]],
    class_name: str | None = None,
) -> type[Component]:
    """
    Membuat lazy-loaded component wrapper.
    
    Args:
        loader: Module path string (e.g., "pages.Profile") atau
                async factory function yang mengembalikan Component class.
        class_name: Nama class target (wajib jika loader adalah string).
    
    Returns:
        Component subclass yang menunda import hingga render pertama.
    """
```

**State Machine di Level Class:**

```
                         ┌──────────────┐
                         │     IDLE     │
                         │ _resolved=None│
                         │ _loading=False│
                         └──────┬───────┘
                                │ render() dipanggil
                                │ _start_loading()
                                ▼
                         ┌──────────────┐
                         │   LOADING    │
                         │ _loading=True │──── raise SuspensePending
                         └──────┬───────┘
                       ┌────────┴────────┐
                       │                 │
                 await sukses      await gagal
                       │                 │
                       ▼                 ▼
                ┌──────────────┐  ┌──────────────┐
                │   RESOLVED   │  │    ERROR     │
                │ _resolved=Cls │  │ _error=exc   │
                └──────────────┘  └──────────────┘
                       │                 │
                 render() → h()    raise _error
                 (normal flow)   (→ Error Boundary)
```

**Implementasi Inti:**

```python
class _LazyBase(Component):
    """Base class internal untuk semua lazy wrapper."""
    _resolved: ClassVar[type | None] = None
    _loading: ClassVar[bool] = False
    _error: ClassVar[Exception | None] = None
    _loader: ClassVar[Callable]
    _subscribers: ClassVar[list[Callable[[], None]]]
    
    @classmethod
    def _start_loading(cls) -> None:
        """Memulai async import. Dipanggil sekali saat render pertama."""
        if cls._loading:
            return
        cls._loading = True
        
        async def _do_load() -> None:
            try:
                resolved_class = await cls._loader()
                cls._resolved = resolved_class
                # Re-inject CSS jika komponen memiliki scoped styles
                _reinject_css_if_needed()
            except Exception as e:
                cls._error = e
            finally:
                cls._loading = False
                # Notifikasi semua Suspense boundary yang subscribe
                for callback in cls._subscribers:
                    callback()
                cls._subscribers.clear()
        
        import asyncio
        asyncio.ensure_future(_do_load())
    
    def render(self) -> VNode:
        cls = self.__class__
        
        # State: RESOLVED → render komponen asli
        if cls._resolved is not None:
            props = dict(self.props)
            props.pop("key", None)   # key milik wrapper, bukan inner
            children = props.pop("children", [])
            return h(cls._resolved, props, children)
        
        # State: ERROR → lempar ke Error Boundary
        if cls._error is not None:
            raise cls._error
        
        # State: IDLE/LOADING → mulai loading, sinyal Suspense
        cls._start_loading()
        raise SuspensePending(cls)
```

**Fungsi `lazy()` sebagai class factory:**

```python
def lazy(loader, class_name=None):
    # Normalisasi loader string menjadi async callable
    if isinstance(loader, str):
        module_path = loader
        if class_name is None:
            raise ValueError("class_name wajib jika loader berupa module path string")
        
        async def _default_loader():
            import importlib
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        
        actual_loader = _default_loader
    else:
        actual_loader = loader
    
    # Buat class baru per pemanggilan lazy()
    display_name = class_name or "LazyComponent"
    
    LazyWrapper = type(display_name, (_LazyBase,), {
        "_resolved": None,
        "_loading": False,
        "_error": None,
        "_loader": staticmethod(actual_loader),
        "_subscribers": [],
    })
    
    return LazyWrapper
```

### 4.3 `Suspense` Boundary Component

```python
class Suspense(Component):
    """
    Boundary component yang menangkap SuspensePending dari komponen
    lazy turunannya dan menampilkan fallback UI selama loading.
    
    Props:
        fallback: VNode | str — UI yang ditampilkan saat loading.
                  Default: <div></div> (kosong).
        children: Konten utama (berisi lazy component).
    """
    
    _is_suspense_boundary: ClassVar[bool] = True
    
    def setup(self):
        self._state = {"pending": False}
        self._pending_lazies: set[type] = set()
    
    def _register_pending(self, lazy_class: type) -> None:
        """Dipanggil oleh _expand_tree saat SuspenseCaughtByBoundary ditangkap."""
        if lazy_class not in self._pending_lazies:
            self._pending_lazies.add(lazy_class)
            lazy_class._subscribers.append(self._on_resolved)
    
    def _on_resolved(self) -> None:
        """Callback saat salah satu lazy component selesai loading."""
        # Hapus yang sudah resolved/error dari tracking set
        self._pending_lazies = {
            lc for lc in self._pending_lazies
            if lc._resolved is None and lc._error is None
        }
        # Trigger re-render (meskipun masih ada yang pending,
        # re-render akan memproses yang sudah resolved dan
        # menangkap SuspensePending lagi untuk sisanya)
        self.set_state({"pending": len(self._pending_lazies) > 0})
    
    def _get_fallback_vnode(self) -> VNode:
        """Menghasilkan VNode fallback dari prop."""
        fallback = self.props.get("fallback")
        if fallback is None:
            return h("div", {}, [])
        if isinstance(fallback, str):
            from pyon.core.template import tokenize, parse, render_element
            tokens = tokenize(fallback)
            ast = parse(tokens)
            return render_element(ast, self, {})
        if isinstance(fallback, type) and issubclass(fallback, Component):
            return h(fallback, {})
        return fallback  # Sudah VNode
    
    def render(self) -> VNode:
        # Selalu kembalikan children slot.
        # Mekanisme Suspense BUKAN di render(), melainkan di _expand_tree.
        children = self.props.get("children", [])
        if len(children) == 1:
            return children[0]
        return h("#fragment", {}, children)
```

### 4.4 Modifikasi `_expand_tree()`

Perubahan pada blok exception handling di `_expand_tree()`:

```python
# === EXISTING ===
except ErrorCaughtByBoundary as e_boundary:
    # ... (tidak berubah) ...

# === NEW: Suspense Boundary Handling ===
except SuspenseCaughtByBoundary as e_suspense:
    if full_key == e_suspense.boundary_key:
        # 1. Register lazy class ke Suspense instance
        instance._register_pending(e_suspense.lazy_class)
        
        # 2. Pre-trigger loading untuk lazy sibling lain
        #    (optimasi: mengurangi waterfall sequential loading)
        _preload_lazy_descendants(child_vnode)
        
        # 3. Render fallback sebagai pengganti
        fallback_vnode = instance._get_fallback_vnode()
        expanded = _expand_tree(
            fallback_vnode, path, full_key,
            component_map, app, _seen_keys
        )
        expanded.component_key = full_key
        expanded.key = node.key
        return expanded
    else:
        raise e_suspense

# === MODIFIED: Generic Exception Handler ===
except Exception as e:
    # --- Existing: Error Boundary search ---
    boundary_key = None
    curr_key = parent_key
    while curr_key:
        parent_instance = component_map.get(curr_key)
        if parent_instance and type(parent_instance).component_did_catch \
                is not Component.component_did_catch:
            boundary_key = curr_key
            break
        if "." in curr_key:
            curr_key = curr_key.rsplit(".", 1)[0]
        else:
            curr_key = ""
    if boundary_key:
        raise ErrorCaughtByBoundary(boundary_key, e)
    
    # --- NEW: Suspense Boundary search ---
    if isinstance(e, SuspensePending):
        suspense_key = None
        curr_key = parent_key
        while curr_key:
            parent_instance = component_map.get(curr_key)
            if parent_instance and getattr(parent_instance,
                    "_is_suspense_boundary", False):
                suspense_key = curr_key
                break
            if "." in curr_key:
                curr_key = curr_key.rsplit(".", 1)[0]
            else:
                curr_key = ""
        if suspense_key:
            raise SuspenseCaughtByBoundary(suspense_key, e.lazy_class)
        else:
            raise RuntimeError(
                f"Lazy component memerlukan boundary <Suspense>. "
                f"Bungkus dengan: <Suspense fallback='...'>...</Suspense>"
            )
    
    raise e
```

#### Fungsi Helper: `_preload_lazy_descendants()`

```python
def _preload_lazy_descendants(node: VNode) -> None:
    """
    Scan VNode tree dan trigger _start_loading() untuk semua
    lazy component yang ditemukan tanpa melakukan instansiasi.
    
    Tujuan: Mengurangi waterfall effect saat multiple lazy 
    component berada di bawah satu Suspense boundary.
    """
    if isinstance(node.tag, type) and hasattr(node.tag, '_resolved'):
        if node.tag._resolved is None and not node.tag._loading:
            node.tag._start_loading()
    
    for child in node.children:
        if isinstance(child, VNode):
            _preload_lazy_descendants(child)
```

### 4.5 Re-injeksi CSS untuk Komponen Lazy

Saat modul lazy di-load, `Component.__init_subclass__()` mengeksekusi dan mendaftarkan CSS baru ke `CSSManager`. Namun stylesheet DOM hanya di-inject sekali saat `App.mount()`.

**Solusi**: Panggil ulang `inject_scoped_css` di dalam `_do_load()`:

```python
def _reinject_css_if_needed():
    """Dipanggil setelah lazy component berhasil di-resolve."""
    from pyon.core.css import CSSManager
    from pyon.dom.css import inject_scoped_css
    
    registry = CSSManager.get_all()
    if registry:
        inject_scoped_css(registry)
```

---

## 5. Alur Eksekusi Lengkap

### 5.1 Initial Mount dengan Lazy Component

```
User → App.mount()
  → _expand_tree(root_vnode)
    → ... proses komponen normal ...
    → _expand_tree(Suspense_vnode)
      → Suspense.__init__(), setup(), component_map["App.Suspense"] = instance
      → Suspense._render() → returns children slot (berisi LazyProfile)
      → try:
          _expand_tree(children)
            → _expand_tree(LazyProfile_vnode)
              → LazyProfile.__init__(), component_map["App.Suspense.LazyProfile"] = instance
              → LazyProfile._render() → render()
              → _resolved == None → _start_loading() → raise SuspensePending
              → except SuspensePending:
                  → walk up: "App.Suspense" → _is_suspense_boundary = True ✓
                  → raise SuspenseCaughtByBoundary("App.Suspense", LazyProfile)
        except SuspenseCaughtByBoundary:
          → boundary_key == full_key ✓
          → _register_pending(LazyProfile class)
          → _preload_lazy_descendants(children)  ← trigger sibling lazy juga
          → fallback_vnode = _get_fallback_vnode()
          → expanded = _expand_tree(fallback_vnode, ...)
          → return expanded  (fallback tree)
    
  → current_tree = expanded fallback tree
  → full_render(current_tree, ...) → DOM menampilkan fallback
  → drain pending_mounts → Suspense.on_mount() dipanggil
```

### 5.2 Resolusi Async & Re-render

```
[Microtask / Event Loop]
  → await loader() berhasil
  → LazyProfile._resolved = ProfileComponent
  → _reinject_css_if_needed()  ← update stylesheet
  → Notifikasi subscribers:
    → Suspense._on_resolved()
      → set_state({"pending": False})
      → _enqueue_dirty() → schedule_flush()
      
[Microtask Flush]
  → flush_updates() → Suspense.execute_update()
  → _schedule_update() → _update_from_key("App.Suspense")
    → keys_before = {"App.Suspense.LazyProfile"}
    → Suspense._render() → children slot (sama)
    → _expand_tree(children)
      → LazyProfile instance sudah di component_map → reuse
      → LazyProfile._render() → render()
      → _resolved != None → return h(ProfileComponent, props)
      → _expand_tree(ProfileComponent_vnode)
        → ProfileComponent.__init__(), setup(), ...
        → ProfileComponent._render() → actual VNode tree
    → new_branch = actual content tree
    
    → keys_in_new = {"App.Suspense.LazyProfile", "App.Suspense.LazyProfile.Profile"}
    → orphan_keys = {} (kosong — LazyProfile masih ada di tree)
    
    → old_branch = fallback tree (dari current_tree)
    → patches = diff(fallback, actual_content)
    → apply_patches(...) → DOM: fallback diganti konten asli
    → _set_vnode_by_path(current_tree, ...)
    → _sync_dom_paths(...)
    → drain pending_mounts → ProfileComponent.on_mount()
```

### 5.3 Multiple Lazy Children (Waterfall Optimization)

```
<Suspense>
  <LazyA />     ← belum loaded
  <LazyB />     ← belum loaded  
  <LazyC />     ← belum loaded
</Suspense>
```

**Tanpa optimasi (sequential waterfall):**
1. Render → LazyA raises SuspensePending → fallback
2. LazyA resolves → re-render → LazyA OK, LazyB raises → fallback lagi
3. LazyB resolves → re-render → LazyA OK, LazyB OK, LazyC raises → fallback lagi
4. LazyC resolves → re-render → semua OK → konten tampil

**Dengan `_preload_lazy_descendants()` (parallel loading):**
1. Render → LazyA raises SuspensePending
2. **`_preload_lazy_descendants()` scan children → trigger LazyB._start_loading() & LazyC._start_loading()**
3. Semua 3 loading berjalan parallel
4. LazyA resolves → re-render → jika B & C sudah resolved juga → konten langsung tampil
5. Jika belum semua → fallback, tunggu sisanya → re-render lagi

---

## 6. File yang Diubah

| # | File | Perubahan | Skala |
|---|---|---|---|
| 1 | `pyon/core/lazy.py` | **Baru** — `lazy()`, `_LazyBase`, `SuspensePending` | File baru |
| 2 | `pyon/core/suspense.py` | **Baru** — `Suspense`, `SuspenseCaughtByBoundary` | File baru |
| 3 | `pyon/core/app.py` | Modifikasi `_expand_tree()` — tambah exception handler | ~40 baris |
| 4 | `pyon/core/app.py` | Tambah `_preload_lazy_descendants()` helper | ~15 baris |
| 5 | `pyon/core/__init__.py` | Export `lazy`, `Suspense` | 2 baris |
| 6 | `pyon/dom/css.py` | Pastikan `inject_scoped_css` bersifat idempotent/incremental | ~5 baris |
| 7 | `pyon/router/core.py` | Update `RouteDef` type: `component: type \| LazyComponent` | ~3 baris |

**File yang TIDAK berubah:**
- `pyon/core/differ.py` — Differ bekerja pada expanded HTML VNode tree; lazy component sudah ter-resolve atau di-fallback sebelum diffing.
- `pyon/dom/render.py` — DOM builder tidak perlu tahu tentang lazy; ia menerima VNode yang sudah final.
- `pyon/dom/patch.py` — Patch executor tidak berubah.
- `pyon/core/template.py` — Template parser me-resolve tag uppercase ke class via `eval_expr()`. `lazy()` mengembalikan class, jadi template parser otomatis kompatibel.

---

## 7. Fase Implementasi

### Fase 1: Core Primitives
1. Buat `pyon/core/lazy.py` — `lazy()`, `_LazyBase`, `SuspensePending`
2. Buat `pyon/core/suspense.py` — `Suspense`, `SuspenseCaughtByBoundary`
3. Export dari `pyon/core/__init__.py`

### Fase 2: Tree Expansion Integration
4. Modifikasi `_expand_tree()` di `pyon/core/app.py`:
   - Tambah `except SuspenseCaughtByBoundary` handler
   - Tambah `SuspensePending` detection di generic `except Exception`
   - Tambah `_preload_lazy_descendants()` helper

### Fase 3: CSS Re-injection
5. Pastikan `inject_scoped_css()` di `pyon/dom/css.py` bersifat incremental (tidak duplikasi rules yang sudah ada)
6. Panggil `_reinject_css_if_needed()` di `_do_load()` setelah resolusi berhasil

### Fase 4: Router Integration
7. Update `RouteDef` di `pyon/router/core.py` untuk menerima lazy component
8. `RouterView.render()` otomatis kompatibel karena `h(lazy_class, props)` menghasilkan VNode yang valid

### Fase 5: Testing & Documentation
9. Buat contoh penggunaan di README.md
10. Update ARCHITECTURE.md dengan alur Suspense

---

## 8. Edge Cases & Pertimbangan

### 8.1 Lazy Component Instance di `component_map`

Saat `SuspensePending` dilempar, instance `_LazyBase` **sudah** terdaftar di `component_map` (karena instansiasi terjadi sebelum `_render()`). Ini **disengaja**:

- **Keuntungan**: Saat resolusi, `_expand_tree` menemukan key yang sama → reuse instance → state machine tetap konsisten.
- **Orphan safety**: Saat Suspense menampilkan fallback, `_update_from_key` pada Suspense level melihat LazyWrapper key di `keys_before` DAN di `keys_in_new` (karena children slot selalu mengandung `<LazyProfile />`). Tidak ada orphan palsu.

### 8.2 Nested Suspense

```
<Suspense fallback="<p>Outer loading...</p>">
    <Suspense fallback="<p>Inner loading...</p>">
        <LazyProfile />
    </Suspense>
    <LazySettings />
</Suspense>
```

`SuspensePending` dari `LazyProfile` → walk up → menemukan **inner** Suspense (terdekat). Inner Suspense menampilkan fallback. Outer Suspense tetap menampilkan konten.

`SuspensePending` dari `LazySettings` → walk up → melewati inner Suspense (bukan ancestor langsung) → menemukan **outer** Suspense. Outer Suspense menampilkan fallback.

### 8.3 Error Selama Loading

Jika `await loader()` melempar exception:
1. `_LazyBase._error` diset
2. Subscriber (Suspense) di-notifikasi → Suspense re-render
3. `_expand_tree` memproses LazyWrapper → `render()` → `raise _error`
4. Exception ditangkap oleh Error Boundary (jika ada) atau propagasi ke atas

### 8.4 Hot Reload Compatibility

Saat hot reload:
- `snapshot_for_hot_reload()` menyimpan state komponen
- Lazy wrapper instance di-snapshot (state machine class-level tetap utuh)
- Setelah reload: jika modul lazy sudah pernah loaded, `_resolved` masih terisi → tidak perlu re-fetch

### 8.5 Template Parser Compatibility

Template parser (`eval_expr`) me-resolve tag uppercase menjadi class dari modul globals:

```python
# Di render_element():
if tag[0].isupper():
    tag = eval_expr(tag, instance, local_scope)
```

`lazy()` mengembalikan class → `eval_expr("LazyProfile", ...)` menghasilkan class `_LazyBase` subclass → `h(LazyWrapper, props)` → VNode valid. **Tidak ada perubahan pada template parser.**

### 8.6 Memory & Proxy Cleanup

- Lazy wrapper instance memiliki lifecycle normal (termasuk `on_unmount` → `_cleanups`)
- Resolved component instance juga memiliki lifecycle normal
- `Suspense._subscribers` dibersihkan setelah notifikasi (`cls._subscribers.clear()`)
- Jika Suspense di-unmount sebelum resolusi → subscription menjadi no-op (Suspense sudah tidak `_mounted`)

---

## 9. Perbandingan dengan React

| Aspek | React | PyOn-Py (Rancangan) |
|---|---|---|
| API | `React.lazy(() => import(...))` | `lazy("module.path", "ClassName")` |
| Boundary | `<Suspense fallback={...}>` | `<Suspense fallback="...">` |
| Mekanisme | Internal fiber reconciler "throws promise" | Exception-based stack unwinding (pattern yang sama dengan Error Boundary) |
| Multiple pending | Concurrent mode tracks promises | Sequential + `_preload_lazy_descendants()` parallel trigger |
| CSS | CSS-in-JS / external | Scoped CSS re-injection via `CSSManager` |
| SSR | Streamable Suspense | N/A (client-only Pyodide) |
