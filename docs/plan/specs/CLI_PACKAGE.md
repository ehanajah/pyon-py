# Spesifikasi CLI & Pemaketan Framework PyOn-Py

Dokumen ini mendeskripsikan arsitektur transformasi PyOn-Py dari folder skrip (*embedded framework*) menjadi paket Python standar yang dapat diinstal (didistribusikan via PyPI) beserta antarmuka baris perintah (*Command Line Interface* / CLI).

---

## 1. Arsitektur Struktur Repositori (End-State)

Setelah pemisahan repositori (Fase 2), repositori utama `pyon-py` hanya akan berisi kode kerangka kerja:

```text
pyon-py/
├── pyon/
│   ├── __init__.py
│   ├── core/           # Engine VDOM, Lifecycle, Batching
│   ├── dom/            # Browser DOM bridging
│   ├── http/           # HTTP Client abstraction
│   ├── router/         # SPA Router
│   ├── dev_server/     # Local development server & offline utilities
│   │   ├── __init__.py
│   │   ├── server.py
│   │   ├── download_pyodide.py
│   │   └── download_packages.py
│   └── cli/            # Antarmuka baris perintah (CLI) berbasis Click
│       ├── __init__.py
│       ├── main.py     # Entry point utama (Grup Click)
│       ├── dev.py      # Implementasi perintah 'pyon dev'
│       ├── download.py # (Akan datang) Implementasi perintah 'pyon download'
│       ├── run.py      # (Akan datang) Implementasi perintah 'pyon run'
│       ├── build.py    # (Akan datang) Implementasi perintah 'pyon build'
│       └── init.py     # Implementasi perintah 'pyon init'
├── pyproject.toml      # Konfigurasi build & distribusi paket
├── README.md
└── .gitignore
```

---

## 2. Command Line Interface (CLI)

CLI `pyon` dibangun menggunakan library `click`. Ini adalah satu-satunya antarmuka masuk (*entry point*) yang akan digunakan developer untuk mengorkestrasi alur kerja PyOn-Py.

### 2.1 Perintah Inti (Fase 1)

| Perintah | Deskripsi | Aksi Internal |
|---|---|---|
| `pyon dev` | Menjalankan peladen pengembangan (*dev server*). | Menjalankan `asyncio.run(main())` dari modul `pyon.dev_server.server`. Otomatis mengaktifkan Hot Reload Inkremental. |
| `pyon add` | Menambah dependensi. | (Lihat [Spesifikasi Dependensi](file:///home/rnd/Documents/projects/pyon-py/docs/plan/specs/DEPENDENCY_MANAGEMENT.md)) Mengunduh dan meregistrasi dependensi ke `pyon.toml`. |
| `pyon download` | Menjalankan proses pengunduhan dependensi *offline*. | (Lihat [Spesifikasi Dependensi](file:///home/rnd/Documents/projects/pyon-py/docs/plan/specs/DEPENDENCY_MANAGEMENT.md)) Mengecek `pyon.toml` dan mengunduh roda (*wheels*) murni ke folder `.gitignore` (`packages_cache/`, `pyodide_local/`). |
| `pyon run <script>` | Menjalankan *custom script* yang didefinisikan. | Membaca blok `[scripts]` dari `pyon.toml` (mirip dengan `npm run`) dan mengeksekusinya via `subprocess.run()`. |

### 2.2 Perintah Lanjutan (Fase 5 - Ditunda)

| Perintah | Deskripsi |
|---|---|
| `pyon build` | Mempersiapkan aplikasi untuk produksi (*production ready*). Menyatukan/minifikasi kode dan aset, serta menghasilkan direktori `dist/` yang siap disajikan via CDN atau Nginx statis. |
| `pyon init <nama>` | *Scaffolding* instan. Menggandakan repositori contoh (seperti `pyon-starter`) yang bersih beserta `pyon.toml` bawaan. |

---

## 3. Konfigurasi `pyproject.toml` (Paket)

File ini mendeskripsikan meta-data dan titik masuk paket (jangan tertukar dengan `pyon.toml` yang merupakan pengaturan spesifik aplikasi dari sudut pandang *developer/user*).

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "pyon-py"
version = "0.1.0"
description = "Python VDOM Framework on Pyodide & WebAssembly"
requires-python = ">=3.11"
dependencies = [
    "aiohttp>=3.9",
    "watchfiles>=0.21",
    "click>=8.0"
]
readme = "README.md"
license = { text = "MIT" }

[project.scripts]
pyon = "pyon.cli.main:cli"
```

Deklarasi `[project.scripts]` di atas sangat vital karena pip/uv akan mengompilasi program binari bernama `pyon` ke dalam PATH sistem, menunjuk ke grup perintah *click* di `pyon.cli.main:cli`.

---

## 4. Alur Publikasi Lintas-Fase (Release Lifecycle)

Siklus hidup publikasi ini menjamin pemisahan lingkungan pengembangan dari kerangka kerja itu sendiri, menciptakan *Developer Experience* (DX) yang lazim.

1. **Pemaketan Hibrida:** Sebelum repositori dibelah, cabang `develop` digunakan untuk menguji integrasi CLI secara penuh menggunakan `pip install -e .` (Instalasi dapat diedit/Editable install).
2. **Isolasi Repositori:** Modul `pyon/` diisolasi menjadi repositori terpisah (`pyon-py-repo`), memisahkannya secara fundamental dari kode implementasi (contoh: `app.py`).
3. **Pengujian Staging:** Artefak didorong (*push*) ke **TestPyPI** terlebih dahulu, membuktikan bahwa skema instalasi `pip install --index-url https://test.pypi.org/simple/ pyon-py` sukses melarutkan (*resolve*) paket pihak ketiga (`aiohttp`, dll).
4. **Rilis Publik (v0.1.0):** Publikasi resmi ke PyPI. Repositori contoh pengguna diubah agar mengimpor via `import pyon` murni alih-alih mengandalkan folder proyek tersemat.
5. **Otomatisasi:** Implementasi Github Actions untuk melempar rilis ke PyPI secara otomatis setiap kali ada pergeseran *tag* semantik git (misal `git tag -a v0.2.0`).
