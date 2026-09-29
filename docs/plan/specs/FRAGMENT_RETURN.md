# Fragment Return Support — Design Spec

## 1. Masalah

Saat ini, `render()` **harus** mengembalikan tepat satu VNode root. Jika template memiliki banyak elemen root, `template.py` melempar `TemplateError`:

```python
# template.py L256-262 — saat ini MENOLAK multi-root
if tag == "#fragment":
    real = [c for c in children if not (isinstance(c, str) and c.strip() == "")]
    if len(real) == 1 and isinstance(real[0], VNode):
        return real[0]
    raise TemplateError("Fragment must contain exactly one VNode...")
```

Kendala fundamental: **seluruh arsitektur path-based** (`_dom_path`, `_get_element_by_path`, differ, patch) berasumsi bahwa satu komponen = satu node DOM root. Fragment membutuhkan banyak node root.

---

## 2. Analisis Strategi

### Strategi A: `display: contents` Wrapper (Pragmatis)

Ganti tag `#fragment` dengan elemen DOM nyata (`<pyon-fragment>`) yang menggunakan CSS `display: contents`.

**Cara kerja `display: contents`:**
- Elemen **tidak menghasilkan kotak visual** (box) sama sekali
- Anak-anaknya dirender seolah-olah mereka adalah anak langsung dari parent
- Elemen tetap ada di DOM tree (bisa di-querySelector, punya childNodes)
- Didukung semua browser modern (Chrome 65+, Firefox 37+, Safari 11.1+)

**Dampak arsitektur: ZERO.**
- `_dom_path` tetap satu string per komponen ✅
- `_get_element_by_path` tetap bekerja (karena node DOM nyata ada) ✅
- `differ.py` tidak perlu diubah (tag `pyon-fragment` diperlakukan seperti `div`) ✅
- `_sync_dom_paths` tidak perlu diubah ✅
- `build_path_owner_map` tidak perlu diubah ✅

**Trade-off:**
- Ada satu elemen ekstra di DOM (tapi invisible secara visual)
- CSS selector masih bisa mencocokkan elemen ini (mitigasi: gunakan `[data-pyon-fragment]` attribute)
- Beberapa edge case CSS seperti `:first-child` bisa terpengaruh (karena parent sebenarnya melihat `<pyon-fragment>` sebagai child, bukan anak langsung di dalamnya)

### Strategi B: True Transparent Fragment (Deep Rewrite)

Fragment benar-benar transparan — tidak ada node DOM, children di-splice ke parent.

**Dampak arsitektur: MASIF.**
- `_dom_path` harus berubah menjadi `list[str]` (satu komponen = banyak path)
- `_get_element_by_path` harus menangani fragment skip
- `differ.py` harus menangani "virtual node tanpa DOM counterpart"
- `_sync_dom_paths` harus melacak multi-path
- `build_path_owner_map` harus memetakan range path
- Path numbering bergeser (fragment di index 1 dengan 3 anak → sibling berikutnya bergeser dari index 2 ke index 4)

**Estimasi risiko:** Tinggi. Perombakan ini menyentuh ~80% core engine.

---

## 3. Rekomendasi: Strategi A (`display: contents`)

Strategi A memberikan **100% fungsionalitas fragment** yang dibutuhkan developer (multi-root render, tanpa wrapper div) dengan **0% perubahan arsitektur**.

Berikut rencana implementasi:

---

## 4. Rencana Implementasi

### Fase 1: Template Parser (`pyon/core/template.py`)

**File:** `pyon/core/template.py` (L256-262)

**Perubahan:** Hapus validasi yang melempar `TemplateError` untuk multi-root. Kembalikan `VNode(tag="pyon-fragment", ...)` secara langsung.

```python
# SEBELUM
if tag == "#fragment":
    real = [c for c in children if not (isinstance(c, str) and c.strip() == "")]
    if len(real) == 1 and isinstance(real[0], VNode):
        return real[0]
    raise TemplateError("Fragment must contain exactly one VNode...")

# SESUDAH
if tag == "#fragment":
    real = [c for c in children if not (isinstance(c, str) and c.strip() == "")]
    if len(real) == 1 and isinstance(real[0], VNode):
        return real[0]  # Optimasi: unwrap jika hanya satu root
    return VNode(tag="pyon-fragment", props={}, children=real)
```

### Fase 2: Component `_render()` (`pyon/core/component.py`)

**File:** `pyon/core/component.py` (L351)

**Perubahan:** Ganti tag `#fragment` menjadi `pyon-fragment`.

```python
# SEBELUM
return h("#fragment", {}, vnode_dict_or_list)

# SESUDAH
return h("pyon-fragment", {}, vnode_dict_or_list)
```

Juga tambahkan dukungan agar `render()` bisa langsung me-return `list[VNode]`:

```python
@final
def _render(self) -> VNode:
    raw_result = self.render()
    
    # Render returns list → wrap in fragment
    if isinstance(raw_result, list):
        return h("pyon-fragment", {}, raw_result)
    
    # Render returns string template
    if isinstance(raw_result, str):
        # ... existing template logic ...
    
    return raw_result
```

### Fase 3: DOM Bridge (`pyon/dom/render.py`)

**File:** `pyon/dom/render.py` (L41-56)

**Perubahan:** Tangani tag `pyon-fragment` secara khusus di `_build_dom_element`. Injeksi CSS `display: contents` langsung.

```python
def _build_dom_element(node, path_owner_map, flush_callback, current_path="0"):
    owner = path_owner_map.get(current_path)
    el = js.document.createElement(str(node.tag))
    
    # Fragment: sembunyikan wrapper secara visual
    if node.tag == "pyon-fragment":
        el.style.display = "contents"
        el.setAttribute("data-pyon-fragment", "")
    
    _apply_props(el, node.props, flush_callback=flush_callback, owner=owner, node=node)
    # ... rest unchanged ...
```

### Fase 4: Injeksi CSS Global (Opsional, untuk keamanan)

**File:** `pyon/dom/render.py` — di dalam `full_render()`

Tambahkan style rule sekali saat mount pertama:

```python
def full_render(tree, selector, flush_callback, component_map=None):
    container = js.document.querySelector(selector)
    # ...
    
    # Inject fragment CSS rule once
    if not hasattr(js.window, "__pyon_fragment_css"):
        style = js.document.createElement("style")
        style.textContent = "pyon-fragment { display: contents; }"
        js.document.head.appendChild(style)
        js.window.__pyon_fragment_css = True
    
    # ... rest unchanged ...
```

### Fase 5: CSS Scoping (`pyon/core/app.py`)

**File:** `pyon/core/app.py` — fungsi `_apply_css_scope()`

**Perubahan:** Jika root VNode dari `render()` adalah `pyon-fragment`, scope attribute (`data-v-xxx`) harus diterapkan ke **anak-anak** fragment, bukan ke fragment itu sendiri.

```python
def _apply_css_scope(node, scope_id):
    if node.tag == "pyon-fragment":
        # Fragment: apply scope to direct children instead
        for child in node.children:
            if isinstance(child, VNode):
                _apply_css_scope(child, scope_id)
    else:
        node.props[scope_id] = ""
        for child in node.children:
            if isinstance(child, VNode):
                _apply_css_scope(child, scope_id)
```

---

## 5. File yang Terpengaruh

| File | Perubahan | Tingkat Risiko |
|------|-----------|----------------|
| `pyon/core/template.py` | Hapus TemplateError, return `pyon-fragment` VNode | Rendah |
| `pyon/core/component.py` | Ganti `#fragment` → `pyon-fragment`, dukung `list` return | Rendah |
| `pyon/dom/render.py` | Inject `display: contents` + CSS rule | Rendah |
| `pyon/core/app.py` | CSS scope propagation untuk fragment | Sedang |
| `pyon/core/differ.py` | **Tidak ada perubahan** | — |
| `pyon/dom/patch.py` | **Tidak ada perubahan** | — |

---

## 6. Contoh Penggunaan (Setelah Implementasi)

### Template Syntax (Multi-root)
```python
class NavItems(Component):
    def render(self):
        return """
        <li>Home</li>
        <li>About</li>
        <li>Contact</li>
        """
```

### Programmatic (List return)
```python
class NavItems(Component):
    def render(self):
        return [
            h("li", {}, ["Home"]),
            h("li", {}, ["About"]),
            h("li", {}, ["Contact"]),
        ]
```

### Hasil DOM
```html
<ul>
    <!-- pyon-fragment secara visual tidak terlihat -->
    <pyon-fragment style="display: contents" data-pyon-fragment>
        <li>Home</li>
        <li>About</li>
        <li>Contact</li>
    </pyon-fragment>
</ul>
```

Secara visual, identik dengan:
```html
<ul>
    <li>Home</li>
    <li>About</li>
    <li>Contact</li>
</ul>
```

---

## 7. Limitasi yang Diterima

1. **CSS `:first-child` / `:last-child`:** Jika `<pyon-fragment>` adalah child pertama/terakhir dari parent, CSS pseudo-selector akan mencocokkan fragment, bukan anak di dalamnya. Ini adalah trade-off yang sama dengan pendekatan Vue 2 (`<template>`). Mitigasi: gunakan `:first-of-type` atau class-based selector.

2. **Elemen DOM ekstra:** Ada satu node tambahan per fragment di DOM tree. Dampak performa: nyaris nol (satu elemen tanpa box model).

3. **`querySelectorAll("*")`:** Akan menangkap `<pyon-fragment>`. Mitigasi: filter dengan `:not(pyon-fragment)` jika diperlukan.
