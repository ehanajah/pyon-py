# PyOn-Py: Roadmap & Priority To-Do List

Dokumen ini berisi rancangan pengembangan fitur, ide masa depan, dan rekam jejak penyelesaian tugas untuk framework web **PyOn-Py** (Python VDOM Framework on Pyodide & WebAssembly).

---

## Aturan (PENTING!)
Setiap kali ada ide, rancangan, atau fitur baru yang ditambahkan ke dokumen ini ke depannya, **Agent WAJIB mematuhi hukum tata letak berikut:**
1. **Klasifikasi Berdasarkan Prioritas:** Evaluasi dan masukkan ide baru ke bawah salah satu dari tiga kategori prioritas di bawah: **Prioritas 1 (Segera)**, **Prioritas 2 (Menengah)**, atau **Prioritas 3 (Jangka Panjang/Ekosistem)**.
2. **Aturan Posisi ("Selalu setelah task done terakhir"):**
   - Di dalam daftar apa pun, tugas atau item yang **sudah selesai (`[x]`) harus selalu berada di deratan atas** sebagai rekam jejak historis.
   - Tugas baru atau yang **belum dikerjakan (`[ ]`) WAJIB diletakkan tepat setelah item terselesaikan (`[x]`) terakhir** (atau di paling atas jika belum ada yang selesai di kategori tersebut).
   - Jangan pernah menyisipkan item baru (`[ ]`) di atas item yang sudah selesai (`[x]`).

---

## Fondasi Inti yang Sudah Selesai (Completed Core Milestones)

Daftar berikut merekam fitur-fitur fundamental yang telah lunas dikerjakan dan distabilkan (terverifikasi oleh 38 test suite lulus 100%):

- [x] **Core Virtual DOM Engine:** Struktur `VNode`, fungsi helper `h()`, sistem rekonsiliasi berperingkat (*keyed diffing algorithm*), serta generasi instruksi *patch* DOM minimalis (`core/vnode.py` & `core/differ.py`).
- [x] **Component Lifecycle Hooks:** Siklus hidup komponen kelas bergaya reaktif (`__init__`, `on_mount`, `render`, `on_unmount`, `on_update` dengan rekam jejak snapshot `prev_props` & `prev_state`).
- [x] **State Batching & Reactive Wakeup:** Sistem batch update melaui `_dirty` flag & antrean `_updates` untuk mencegah eksekusi re-render redundan saat `set_state()` dipanggil berulang kali dalam siklus yang sama.
- [x] **Error Boundary:** Pengambilan alihan pengecualian runtime melalui `component_did_catch(error)` dan *stack unwinding hierarchy traversal* untuk tampilan fallback yang tangkas.
- [x] **Slot & Composition Pattern:** Injeksi aman `props["children"]` setelah render konstruktor selesai dengan menyalin kamus props (*immutable copying*), mengamankan keakuratan alamat koordinat DOM (`_dom_path`) dan kemurnian render kondisional.
- [x] **Context API & Global Provide:** Fitur pengelompokan context hierarkis melalui isolasi `.copy()` pada `_contexts`, didukung oleh metode `App.provide()` untuk distribusi *global app context*.
- [x] **Refactoring & Pemurnian Codebase:** Penyeragaman impor `VNode` ke level global/modul (menghapus alias temporer) serta penyederhanaan ergonomis dengan menghapus parameter generik `StateT` dari kelas utama `Component[PropsT]`.
- [x] **Async Support (Dukungan Asinkron & Event Handlers):** Mendukung method asinkron (`async def`) yang dieksekusi ke event loop via `asyncio.ensure_future()`, serta `self.set_state()` thread-safe yang aman dari *race condition* paska `await`.
- [x] **SPA Router (Dynamic Navigation & History API):** Sistem routing tanpa *full page reload* (`window.onpopstate`), komponen reaktif `<RouterView>` & `<Link>`, ekstraksi Parameter Dinamis & Query Parameters, serta Halaman 404 & Scroll Restoration.

- [x] **HTTP Client Module (`pyon.http`):** Lapisan pembungkus HTTP asinkron mandiri (`client.py`, `resource.py`, `response.py`) yang terisolasi dengan rapi dari implementasi browser bawaan, sehingga logika jaringan (`get()`, `post()`, dll) bisa dites via `pytest`.
- [x] **Dev Server Dasar (`dev/server.py`):** Peladen HTTP lokal berbasis `aiohttp` dengan auto-generate `loader.js`, *static file serving* + SPA fallback, hot reload via SSE (`watchfiles`), dan auto-scaffold (`index.html` & `app.py`).
- [x] **Hot Reload Inkremental (Tanpa Reload Pyodide):**
  - **Hanya download file yang berubah:** Server mengirim daftar file berubah via SSE; browser *re-fetch* selektif ke *virtual FS*.
  - **Teardown & Invalidate:** Membersihkan `component_map`, mengeksekusi `on_unmount`, lalu menghapus memori *cache* modul proyek (`sys.modules`) sebelum merender ulang aplikasi.
  - **Debounce SSE:** Penyatuan notifikasi multi-file (*save all*) dalam satu rentang waktu.

---

## Prioritas 1: Segera (Mendesak & Bernilai Tinggi untuk Aplikasi Nyata)
*Fokus saat ini: Pemaketan (Packaging) Framework dan Mempercepat Siklus Pengembangan.*

- [ ] **Distribusi PyOn-Py sebagai Package & CLI Tool:**
  - **Fase 1 (Refactoring & CLI):** Membuat direktori `pyon/cli/` berbasis `click` (`dev`, `download`, `run`), memindahkan `dev_server`, dan menambahkan `pyproject.toml` dengan entry point `pyon`.
  - **Fase 2 (Isolasi Repo):** Mengekstrak direktori `pyon/` menjadi repositori murni `pyon-py` yang bersih dari kode implementasi/contoh aplikasi.
  - **Fase 3 (Publikasi PyPI):** Membangun `dist/*` via modul `build` dan mengunggahnya ke TestPyPI lalu PyPI asli (rilis v0.1.0).
- [ ] **Local Pyodide & Dependencies (Offline Dev Environment):**
  - Struktur `pyon.toml` terpusat sebagai satu sumber kebenaran (menggunakan `tomllib` Python 3.11+).
  - Skrip pengunduh mandiri `dev_server/download_pyodide.py` untuk mengunduh runtime Pyodide ke localhost.
  - Skrip pengunduh mandiri `dev_server/download_packages.py` dengan memanfaatkan perintah `pip download` internal guna mengunduh murni roda Python (*pure Python wheels*) **beserta** dependensi turunannya (*transitive dependencies*).
  - Dev server menyajikan file secara luring dari cache `pyodide_local/` dan `packages_cache/` untuk mencapai inisialisasi awal (initial load) kilat <1 detik.
- [ ] **Pembatalan Request HTTP (AbortController):**
  - Mengintegrasikan Javascript `AbortController` ke modul `pyon.http`.
  - Mengaitkan pembatalan ke *lifecycle* komponen. Jika `on_unmount` dipanggil saat request (seperti `fetch`) masih berjalan, *request* wajib dibatalkan otomatis agar tidak memicu `set_state` pada komponen yang telah musnah (mencegah *memory leak* & *exception*).
- [ ] **`ref` untuk Akses DOM Langsung:**
  - Menambahkan dukungan kamus referensi `self.refs = {}` pada komponen kelas.
  - Pembungkus jembatan di `pyodide_impl` secara otomatis menyambungkan elemen DOM asli ke dalam `owner.refs["id_input"]` apabila VNode mendeklarasikan prop `"ref": "id_input"`. Sangat penting untuk fokus elemen (`input.focus()`), pemetaan dimensi, dan integrasi library bagan/grafik pihak ketiga (Chart.js / Canvas).

---

## Prioritas 2: Menengah (Developer Experience / DX & Kemampuan Inti)
*Fokus pada peningakatan produktivitas pengembang, arsitektur data besar, dan kecepatan iterasi lokal.*

- [ ] **Sistem Client Session HTTP Terpusat:**
  - Pembuatan kelas `HTTPClient` (mirip `httpx.Client`) untuk menyimpan konfigurasi *stateful* berulang seperti `base_url`, `default_headers`, atau *Auth Tokens*.
- [ ] **Server-Sent Events (SSE) & WebSockets:**
  - Sub-modul `pyon/http/sse.py` dan `ws.py` untuk mengelola protokol *real-time* dan *streaming*, lengkap dengan status *re-render* yang reaktif.
- [ ] **CSS Scoping Sederhana:**
  - Isolasi gaya presentasi tanpa kompleksitas Shadow DOM melalui injeksi otomatis awalan (*prefix*) nama kelas komponen (misal: `"card-body"` dikomputasi menjadi `"Card-card-body"`), mencegah tabrakan kelas CSS (*style collisions*).

---

## Prioritas 3: Nanti (Ekosistem, Build System & Production Readiness)
*Fokus jangka panjang untuk kesiapan penyampaian produksi berkecepatan tinggi dan kelengkapan infrastruktur perkakas pendukung.*

- [ ] **Build System & Production Optimization (WASM):**
  - Implementasi komandan sistem build untuk produksi yang menonaktifkan fitur pemuat mode dev (*dev tools/server fetching* file per file).
  - Merapikan (minify), memampatkan (bundle), dan menyatukan seluruh berkas Python menjadi satu kesatuan paket kompresi (*virtual filesystem zip*) demi percepatan muat perdana (*initial load payload speed*) yang kilat.
- [ ] **Stateful Hot Reload (Persistensi State & Instance):**
  - Mempertahankan `_state` dan *instance* komponen yang tidak berubah saat hot reload menggunakan `importlib.reload()` dan migrasi `instance.__class__` ke kelas baru.
  - Alternatif lebih sederhana: *snapshot* state sebelum restart, lalu *restore* ke instance baru yang memiliki `component_key` yang sama.
- [ ] **Package & Module System Resolution:**
  - Penyempurnaan manajemen hierarki folder dan modul untuk proyek berskala besar di atas sistem berkas virtual Pyodide TANPA mengandalkan daftar impor linear kaku di `loader.js`.
- [ ] **Template Syntax & Alternatif Penulisan UI:**
  - Penjajakan dukungan sintaksis deklaratif opsional (seperti markup bergaya JSX atau templating HTML transparan) selain penggunaan fungsi murni `h()`.
- [ ] **`wasm_impl.py` (Native WASM / MicroPython Bridge):**
  - Eksplorasi backend jembatan eksekusi alternatif selain Pyodide (misalnya MicroPython untuk WASM atau Python native WASM runtime masa depan) untuk meringankan konsumsi memori dan ukuran bodi runtime.
