# Spesifikasi Lingkungan Pengembangan Lokal (Local Pyodide & Dependencies)

Dokumen ini menjelaskan arsitektur dan alur kerja untuk menjalankan framework PyOn-Py secara *offline* di lingkungan pengembangan lokal (localhost). Tujuan utamanya adalah untuk mengurangi waktu muat pertama (*initial load time*) secara drastis dari ~5-9 detik (menggunakan CDN) menjadi ~0.3-0.8 detik, guna memberikan pengalaman pengembangan kelas-satu (*first-class DX*).

---

## 1. Arsitektur Struktur Folder

```text
pyon-py-project/
├── pyon.toml              ← Single Source of Truth: konfigurasi project, versi, & dependensi
├── pyodide_local/         ← Runtime Pyodide penuh (diunduh sekali via script)
│   ├── pyodide.js
│   ├── pyodide.asm.js
│   ├── pyodide.asm.wasm
│   ├── python_stdlib.zip
│   ├── repodata.json
│   └── packages/          ← Package native/C-extensions bawaan Pyodide (numpy, dll)
├── packages_cache/        ← Cache Pure Python wheels dari PyPI (diunduh sekali via script)
│   └── pure_python/
│       ├── httpx-0.27.0-py3-none-any.whl
│       ├── anyio-4.3.0-py3-none-any.whl
│       └── ...
├── dev/
│   ├── download_pyodide.py
│   ├── download_packages.py
│   └── server.py
└── .gitignore             ← Mengecualikan direktori pyodide_local/ dan packages_cache/
```

> **Catatan Git:** Hanya `pyon.toml` yang perlu dimasukkan ke version control (di-commit). Folder cache berukuran puluhan MB (`pyodide_local` dan `packages_cache`) akan otomatis diabaikan karena tercatat di `.gitignore`. Tim developer lain dapat mereproduksi lingkungan yang persis sama cukup dengan menjalankan kedua skrip utilitas pengunduh.

---

## 2. Konfigurasi `pyon.toml`

Sistem akan menggunakan standar modern `toml` (diproses dengan `tomllib` bawaan Python 3.11+) sebagai pusat kebenaran referensi (*single source of truth*).

```toml
[dependencies]
# Daftar paket PyPI murni yang dibutuhkan aplikasi
packages = ["httpx", "anyio"]

[dev]
pyodide_version = "0.314.0"
local_pyodide   = true
local_packages  = true
```

---

## 3. Skrip Utilitas (One-Time Setup)

Dua skrip ditulis murni dalam Python dan hanya perlu dieksekusi satu kali setiap ada perubahan versi Pyodide atau penambahan pustaka pada `pyon.toml`.

### 3.1 `dev/download_pyodide.py`
Fungsi: Mengunduh runtime Pyodide secara utuh.
Alur Kerja:
1. Membaca `pyodide_version` dari `pyon.toml`.
2. Mengecek apakah `pyodide_local/pyodide.js` sudah memiliki versi yang sama. Jika ya, abaikan (*skip*).
3. Jika belum, unduh arsip rilis tarball (contoh: `pyodide-0.314.0.tar.bz2`) dari halaman rilis GitHub resmi Pyodide.
4. Ekstrak seluruh isinya ke folder `pyodide_local/`.

### 3.2 `dev/download_packages.py`
Fungsi: Mengunduh *pure Python wheels* beserta seluruh **dependensi turunannya**.
Alur Kerja:
1. Membaca properti `packages` dari blok `[dependencies]` di `pyon.toml`.
2. Menghapus semua isi lama di `packages_cache/pure_python/` (opsional, untuk mencegah akumulasi sisa versi lama).
3. Menggunakan modul bawaan `pip` secara programatis untuk mengunduh berkas `.whl` murni ke dalam cache:
   ```bash
   python -m pip download <paket1> <paket2> \
       --dest packages_cache/pure_python/ \
       --only-binary=:all: \
       --platform any \
       --python-version 3.11
   ```
   *Penggunaan flag ini menjamin bahwa hanya wheel pure Python yang ditarik, dan pip secara cerdas meresolusi dependensi turunannya (transitive dependencies).*

---

## 4. Modifikasi Dev Server & Loader (`dev/server.py`)

### 4.1 URL Routing Baru
Server `aiohttp` akan diperluas dengan router statis berikut:
- `GET /pyodide/*` → menyajikan file dari direktori lokal `pyodide_local/`.
- `GET /packages/*` → menyajikan file dari direktori lokal `packages_cache/pure_python/`.
- `GET /*` → menyajikan aplikasi seperti biasa.

### 4.2 Dinamika `loader.js`
Saat diakses, endpoint generator `/loader.js` akan membaca `pyon.toml`. 

**Bila `local_pyodide = true`:**
URL peluncur (indexURL) Pyodide akan dialihkan ke titik akhir lokal.
```javascript
const pyodide = await loadPyodide({
    indexURL: "/pyodide/" 
});
```

**Bila `local_packages = true`:**
Server secara otomatis memindai seluruh *file* berakhiran `.whl` di dalam folder `packages_cache/pure_python/`, dan menyuntikkan lariknya (*array*) ke kode JavaScript:
```javascript
// Data disuntikkan dari backend server.py
const LOCAL_PACKAGES = [
    "/packages/httpx-0.27.0-py3-none-any.whl",
    "/packages/certifi-2024.2.2-py3-none-any.whl", // dependensi turunan yang otomatis diunduh pip
    // ...
];
await micropip.install(LOCAL_PACKAGES);
```

### 4.3 Cache-Busting & Performa
Titik akhir lokal ini **menghindari caching** dari browser saat tahap pengembangan untuk memastikan pembaruan `.whl` segera terbaca, namun dengan kecepatan localhost (0.3s), ketidakhadiran *browser cache* tidak terasa membebani.

---

## 5. Ringkasan Dampak Waktu Eksekusi

| Lingkungan Runtime | Initial Load Time | Latensi Hot Reload |
|---|---|---|
| Murni CDN (Semua aset dari jaringan luar) | ~5.0s - 9.0s | ~3.0s - 6.0s (Full Page Reload) |
| Local Pyodide + Local Dependencies | **~0.3s - 0.8s** | **~200ms - 300ms** (Incremental Reload) |

Kombinasi antara **Local Pyodide** dan **Incremental Hot Reload** (pemuatan ulang sebagian) menyempurnakan alur kerja produktivitas instan seakan murni membangun aplikasi Desktop atau NodeJS.
