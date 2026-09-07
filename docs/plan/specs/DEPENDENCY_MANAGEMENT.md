# Spesifikasi Manajemen Dependency PyOn-Py

Dokumen ini mendeskripsikan arsitektur pengelolaan dependensi dua-lapisan (*two-layer dependency management*) untuk framework PyOn-Py, termasuk perintah CLI terkait, mekanisme di sisi browser, dan format konfigurasi.

Terkait perancangan dasar paket dan perintah-perintah CLI lainnya, lihat [Spesifikasi CLI & Pemaketan Framework](file:///home/rnd/Documents/projects/pyon-py/docs/plan/specs/CLI_PACKAGE.md).

---

## 1. Konsep Inti: Dua Lapisan Dependency

PyOn-Py beroperasi di dua *runtime* yang berbeda secara fundamental. Setiap dependensi harus diklasifikasikan berdasarkan lapisan mana yang membutuhkannya.

### Layer 1 — Host Machine (Development)

- **Diinstal via:** `pip` ke `venv` lokal.
- **Tujuan:** IDE *autocomplete*, *type checking*, *source code navigation*, *dev tools* (`pytest`, `ruff`), dan eksekusi skrip lokal.
- **Mencakup semua dependensi** — baik yang dibutuhkan browser maupun yang murni *development-only*.

### Layer 2 — Browser Runtime (Pyodide)

- **Diinstal via:** `micropip` saat aplikasi dimuat di browser.
- **Tujuan:** Dependensi yang digunakan langsung oleh kode Python yang berjalan di dalam Pyodide/WebAssembly.
- **Subset dari Layer 1** — Tidak semua dependensi Layer 1 masuk ke Layer 2. Paket seperti `pytest`, `ruff`, atau *linter* lainnya **tidak pernah** diinstal di browser.

### Keterbatasan Layer 2

> [!IMPORTANT]
> **Hanya *pure Python wheels*** yang dapat diinstal oleh `micropip` kecuali paket tersebut sudah memiliki build `wasm32` di [Pyodide Package Index](https://pyodide.org/en/stable/usage/packages-in-pyodide.html).
> Paket dengan *C extension* native (contoh: `uvloop`, `psycopg2`) **tidak kompatibel** dengan Pyodide.
> CLI `pyon add` wajib memvalidasi kompatibilitas ini dan memberikan peringatan eksplisit jika paket tidak kompatibel.

---

## 2. `pyon.toml` sebagai Single Source of Truth

Seluruh konfigurasi dependensi terpusat di file `pyon.toml` yang berada di *root* direktori proyek pengguna. File ini dibaca oleh CLI (`pyon add`, `pyon download`) dan oleh *dev server* (untuk menghasilkan `loader.js`).

```toml
[project]
name    = "my-app"
version = "0.1.0"

[dependencies]
# Diinstal di KEDUA lapisan — lokal (pip) DAN browser (micropip)
packages = [
    "httpx>=0.27",
    "anyio>=4.0",
]

[dev-dependencies]
# Diinstal HANYA di lokal (pip) — TIDAK masuk browser
packages = [
    "pytest",
    "pytest-asyncio",
    "ruff",
]

[dev]
port            = 8000
pyodide_version = "0.314.0"
local_pyodide   = true
local_packages  = true
```

### Aturan Pembacaan

| Blok | `pip install` (lokal) | `micropip.install` (browser) | Download wheel ke cache |
|---|:---:|:---:|:---:|
| `[dependencies]` | ✅ | ✅ | ✅ |
| `[dev-dependencies]` | ✅ | ❌ | ❌ |

---

## 3. Perintah CLI

### 3.1 `pyon add` — Tambah Dependency

Menambahkan satu atau lebih paket ke proyek. Secara *default*, paket masuk ke `[dependencies]` (Layer 1 + Layer 2).

```bash
# Dependency runtime (browser + lokal)
pyon add httpx anyio
```

**Aksi internal:**
1. `pip install httpx anyio` — Instal ke `venv` lokal.
2. `pip download --only-binary=:all: --platform any -d packages_cache/ httpx anyio` — Unduh *pure Python wheels* beserta dependensi transitif.
3. Regenerasi `packages_cache/manifest.json`.
4. Tambahkan entri ke `pyon.toml` `[dependencies].packages`.

```bash
# Dependency development-only (lokal saja)
pyon add pytest ruff --dev
```

**Aksi internal:**
1. `pip install pytest ruff` — Instal ke `venv` lokal.
2. **Tidak** mengunduh *wheel* ke `packages_cache/`.
3. Tambahkan entri ke `pyon.toml` `[dev-dependencies].packages`.

### 3.2 `pyon download` — Setup Environment dari `pyon.toml`

Dijalankan saat *clone* repositori baru atau *setup* lingkungan pengembangan dari awal. Satu perintah untuk menyiapkan segalanya.

```bash
pyon download
```

**Aksi internal:**
1. Baca `pyon.toml`.
2. `pip install` semua `[dependencies]` + `[dev-dependencies]` ke `venv` lokal.
3. `pip download` semua `[dependencies]` (saja) ke `packages_cache/`.
4. Regenerasi `packages_cache/manifest.json`.
5. Unduh runtime Pyodide ke `pyodide_local/` (jika `[dev].local_pyodide = true`).

### 3.3 `pyon remove` — Hapus Dependency (Ditunda)

```bash
pyon remove httpx
```

**Aksi internal:**
1. `pip uninstall httpx`.
2. Hapus *wheel* terkait dari `packages_cache/`.
3. Regenerasi `packages_cache/manifest.json`.
4. Hapus entri dari `pyon.toml`.

> [!NOTE]
> Implementasi `pyon remove` ditunda karena kompleksitas pengelolaan *orphan transitive dependencies* (misal: menghapus `httpx` tetapi `idna` masih dibutuhkan oleh paket lain). Untuk saat ini, developer bisa menghapus entri secara manual dari `pyon.toml` dan menjalankan ulang `pyon download`.

---

## 4. Manifest File (`packages_cache/manifest.json`)

Manifest adalah jembatan antara nama paket logis (yang ditulis di `pyon.toml`) dan nama file *wheel* fisik yang ada di disk. File ini di-*generate* secara otomatis oleh `pyon add` dan `pyon download`.

### Struktur Direktori

```
packages_cache/
├── manifest.json                       ← Auto-generated
├── httpx-0.27.0-py3-none-any.whl
├── anyio-4.6.0-py3-none-any.whl
├── idna-3.7-py3-none-any.whl           ← Dependensi transitif httpx
├── sniffio-1.3.1-py3-none-any.whl      ← Dependensi transitif anyio
└── ...
```

### Format Manifest

```json
{
  "generated_at": "2026-09-04T17:30:00+07:00",
  "packages": {
    "httpx": "httpx-0.27.0-py3-none-any.whl",
    "anyio": "anyio-4.6.0-py3-none-any.whl",
    "idna": "idna-3.7-py3-none-any.whl",
    "sniffio": "sniffio-1.3.1-py3-none-any.whl",
    "certifi": "certifi-2024.7.4-py3-none-any.whl"
  }
}
```

### Mekanisme Generasi

Manifest dihasilkan dengan memindai seluruh file `*.whl` di dalam `packages_cache/` dan mengekstrak nama paket dari konvensi penamaan *wheel* standar (`{name}-{version}-{python}-{abi}-{platform}.whl`).

---

## 5. Mekanisme di Sisi Browser

### 5.1 Integrasi dengan `loader.js`

Dev server membaca `pyon.toml` dan meng-*generate* blok instalasi dependensi di dalam `loader.js`:

```javascript
// Auto-generated oleh dev server berdasarkan pyon.toml [dependencies]
const PACKAGES = ["httpx>=0.27", "anyio>=4.0"];
const USE_LOCAL = true;  // dari pyon.toml [dev].local_packages

// Manifest dari packages_cache/manifest.json
const MANIFEST = {
    "httpx": "httpx-0.27.0-py3-none-any.whl",
    "anyio": "anyio-4.6.0-py3-none-any.whl",
    "idna": "idna-3.7-py3-none-any.whl",
    // ... dependensi transitif
};

async function installDependencies(pyodide) {
    const micropip = pyodide.pyimport("micropip");

    if (USE_LOCAL) {
        // Instal SEMUA wheel dari cache lokal (termasuk transitif)
        for (const [name, filename] of Object.entries(MANIFEST)) {
            await micropip.install(`/packages/${filename}`);
        }
    } else {
        // Fallback: instal dari PyPI langsung
        for (const pkg of PACKAGES) {
            await micropip.install(pkg);
        }
    }
}
```

### 5.2 Route Dev Server untuk Menyajikan Wheels

Dev server menyediakan *endpoint* khusus untuk menyajikan file *wheel* dari `packages_cache/`:

```
GET /packages/<filename>.whl  →  packages_cache/<filename>.whl
```

---

## 6. Alur Kerja Developer

### Setup Proyek Baru

```bash
mkdir my-app && cd my-app
pyon init                    # Scaffold pyon.toml, index.html, app.py, src/
pyon add httpx               # Tambah dependency pertama
pyon dev                     # Langsung bisa develop
```

### Clone Repositori yang Sudah Ada

```bash
git clone <repo-url>
cd my-app
python -m venv venv && source venv/bin/activate
pip install pyon-py          # Instal framework
pyon download                # Satu perintah: pip install deps + download wheels + download Pyodide
pyon dev                     # Siap develop
```

### Tambah Dependency di Tengah Development

```bash
pyon add requests            # Install + register + download wheel
# Dev server mendeteksi perubahan pyon.toml → reload otomatis
```

---

## 7. Validasi Kompatibilitas Wheel

Saat `pyon add` dijalankan, CLI melakukan validasi berikut:

1. **Cek ketersediaan *pure Python wheel*:** Jalankan `pip download --only-binary=:all: --platform any` secara *dry-run*. Jika gagal, periksa apakah paket ada di Pyodide Package Index.
2. **Jika tidak kompatibel:** Tampilkan peringatan eksplisit:
   ```
   ⚠ WARNING: Package 'numpy' memiliki C extension dan tidak tersedia
   sebagai pure Python wheel. Package ini TIDAK AKAN berfungsi di browser
   kecuali sudah tersedia di Pyodide Package Index.

   Pyodide built-in: ✅ numpy tersedia (gunakan micropip.install dari CDN)
   ```
3. **Jika tersedia di Pyodide Index tetapi bukan *pure Python*:** Tambahkan ke `pyon.toml` dengan catatan bahwa paket ini hanya bisa diinstal dari CDN Pyodide (bukan dari cache lokal).

---

## 8. File yang Harus Di-`.gitignore`

```gitignore
# Dependency caches (di-generate oleh pyon download / pyon add)
packages_cache/
pyodide_local/

# Build artifacts
pyon_py.egg-info/
```

`manifest.json` berada di dalam `packages_cache/` sehingga otomatis ter-*ignore* juga. Ini aman karena manifest selalu bisa di-regenerasi dari file *wheel* yang ada.

---

## 9. Roadmap Implementasi

| Perintah | Prioritas | Status |
|---|---|---|
| `pyon init` | Segera | ✅ Selesai |
| `pyon dev` | Segera | ✅ Selesai |
| `pyon add` | Segera | ⬜ Belum |
| `pyon download` | Segera | ⬜ Belum |
| `pyon run` | Segera | ⬜ Belum |
| `pyon remove` | Nanti | ⬜ Ditunda |
| `pyon build` | Nanti | ⬜ Ditunda |
