# Spesifikasi Dev Server PyOn-Py

Dokumen ini mendeskripsikan arsitektur, fitur yang telah diimplementasikan, dan rencana pengembangan dari **Dev Server** (`dev/server.py`) untuk framework PyOn-Py.

## 1. Arsitektur Umum

Dev server adalah peladen HTTP lokal berbasis `aiohttp` yang berperan sebagai jembatan antara kode sumber Python di disk dengan mesin runtime Pyodide di browser. Ia bertanggung jawab atas tiga pekerjaan utama:

1. **Menyajikan file statis** (HTML, CSS, JS, `.py`) ke browser.
2. **Men-generate `loader.js`** secara dinamis — skrip JavaScript yang mengorkestra urutan muat Pyodide, dependensi `micropip`, dan semua file `.py` proyek ke *virtual filesystem*.
3. **Menyiarkan notifikasi perubahan file** ke browser melalui protokol SSE (*Server-Sent Events*), sehingga browser bisa bereaksi tanpa polling.

```text
┌─────────────────────┐           SSE /__reload           ┌──────────────┐
│   watchfiles        │  ─── file berubah ──────────────▶ │   Browser    │
│   (filesystem)      │                                   │              │
└─────────────────────┘          HTTP /loader.js          │  Pyodide     │
┌─────────────────────┐ ◀──── request ─────────────────── │  VirtualFS   │
│   aiohttp server    │  ────── response (JS) ──────────▶ │              │
│   (dev/server.py)   │                                   └──────────────┘
└─────────────────────┘
```

---

## 2. Fitur yang Sudah Diimplementasikan

### 2.1 Static File Serving & SPA Fallback
- Menyajikan seluruh file dari `PROJECT_ROOT` melalui HTTP.
- Fallback ke `index.html` untuk rute yang tidak mengembalikan file statis (mendukung SPA client-side routing).
- Perlindungan *path traversal* (`../../etc`).

### 2.2 Auto-generate `loader.js`
- Memindai seluruh file `.py` secara rekursif dari project root.
- Mengurutkan file berdasarkan dependensi: `core/` → `browser/` → `dom/` → `http/` → `router/` → `root`.
- `__init__.py` selalu dimuat duluan di setiap paket agar Python mengenali struktur modul.
- Menghasilkan skrip JavaScript yang:
  1. Memuat Pyodide dari CDN.
  2. Memasang `micropip` dan dependensi pihak ketiga (contoh: `typing-extensions`).
  3. Mengambil (*fetch*) setiap file `.py` dan menulisnya ke *virtual filesystem* Pyodide.
  4. Menjalankan `from app import start; start()`.

### 2.3 Hot Reload via SSE (Full Page Reload)
- `watchfiles` memantau perubahan file `.py` secara *async*.
- Perubahan disiarkan (*broadcast*) ke semua tab browser melalui SSE endpoint `/__reload`.
- Saat ini browser merespons dengan `location.reload()` — **seluruh halaman dimuat ulang dari nol** (termasuk Pyodide, micropip, dan fetch semua file).

### 2.4 Auto-scaffold
- Men-generate `index.html` dan `app.py` minimal jika belum ada, mempercepat onboarding proyek baru.

---

## 3. Prioritas 1: Hot Reload Inkremental (Tanpa Reload Pyodide)

### 3.1 Masalah
Siklus pengembangan saat ini sangat lambat:
1. Developer mengubah 1 baris kode Python.
2. Browser memuat ulang **seluruh halaman**.
3. Pyodide (~5 detik), micropip + install (~2 detik), fetch **semua** file `.py` (~1 detik) dijalankan ulang dari awal.
4. Total waktu iterasi: **~8 detik** untuk perubahan 1 baris.

### 3.2 Sasaran
Mencapai siklus reload di bawah **1 detik** dengan strategi:
1. **Hanya download file yang berubah** — server memberitahu browser *file mana* yang berubah; browser hanya *re-fetch* dan *re-write* file tersebut ke *virtual FS*.
2. **Jangan muat ulang Pyodide & micropip** — cukup *invalidate* modul Python yang berubah di `sys.modules` dan jalankan ulang `app.start()`.

### 3.3 Perubahan di Sisi Server (`dev/server.py`)

#### a) Broadcast Daftar File yang Berubah (Bukan Sinyal Reload Generik)
Ubah payload SSE dari:
```json
{"type": "reload", "file": "src/pages/Home.py"}
```
Menjadi:
```json
{"type": "update", "files": ["src/pages/Home.py", "src/pages/About.py"]}
```
Gunakan debounce (~100ms) setelah `watchfiles` menerima batch perubahan, agar perubahan multi-file (misalnya *save all*) dikirim dalam satu payload tunggal.

#### b) Endpoint Hash Manifest (Opsional/Peningkatan)
Endpoint baru `GET /__manifest` yang mengembalikan peta `{path: hash}` dari semua file `.py`. Browser dapat membandingkan hash lokal (dari *virtual FS*) dengan hash server untuk menentukan file mana yang benar-benar berubah. Berguna saat browser *reconnect* setelah koneksi SSE terputus sementara.

### 3.4 Perubahan di Sisi Client (`loader.js`)

#### a) Pisahkan Inisialisasi dan Restart Aplikasi
Refaktor `initPyOnPy()` menjadi dua fase:

```javascript
// Fase 1: Boot (hanya sekali)
async function boot() {
    window.__pyodide = await loadPyodide();
    window.__pyodide.runPython(`import sys; sys.path.insert(0, "/")`);
    await window.__pyodide.loadPackage("micropip");
    const micropip = window.__pyodide.pyimport("micropip");
    await micropip.install(["typing-extensions"]);
    // Fetch SEMUA file dan tulis ke virtual FS
    await loadAllFiles(PY_FILES);
    await runApp();
}

// Fase 2: Restart (dipanggil setiap ada perubahan file)
async function restart(changedFiles) {
    // 1. Re-fetch HANYA file yang berubah
    for (const filePath of changedFiles) {
        const res = await fetch("/" + filePath + "?t=" + Date.now());
        const code = await res.text();
        window.__pyodide.FS.writeFile(filePath, code);
    }

    // 2. Invalidate modul Python yang berubah dari cache
    window.__pyodide.runPython(`
import sys
changed = ${JSON.stringify(changedFiles)}
for f in changed:
    mod_name = f.replace("/", ".").removesuffix(".py")
    # Hapus modul dan semua sub-modulnya
    to_delete = [k for k in sys.modules if k == mod_name or k.startswith(mod_name + ".")]
    for k in to_delete:
        del sys.modules[k]
    `);

    // 3. Jalankan ulang app
    await runApp();
}
```

#### b) Handler SSE yang Cerdas
```javascript
const _sse = new EventSource("/__reload");
_sse.addEventListener("message", async (e) => {
    const data = JSON.parse(e.data);
    if (data.type === "update") {
        await restart(data.files);
    }
});
```

### 3.5 Perubahan di Sisi Framework (`pyon/core/app.py`)

#### a) Fungsi `runApp()` — Teardown Sebelum Restart
Sebelum memanggil `start()` ulang, framework harus membersihkan state sebelumnya:

```python
# Dipanggil oleh loader.js sebelum menjalankan start() ulang
def teardown():
    # 1. Panggil on_unmount pada seluruh komponen aktif
    for key, instance in app.component_map.items():
        instance._invoke_on_unmount()
    # 2. Kosongkan component_map
    app.component_map.clear()
    # 3. Kosongkan DOM container
    # (dilakukan dari JS: document.getElementById("app").innerHTML = "")
```

Alur lengkap `runApp()`:
```javascript
async function runApp() {
    // Bersihkan DOM
    document.getElementById("app").innerHTML = "";
    // Teardown framework state
    window.__pyodide.runPython("from app import teardown; teardown()");
    // Jalankan ulang aplikasi
    await window.__pyodide.runPythonAsync("from app import start; start()");
}
```

---

## 4. Prioritas Rendah: Stateful Hot Reload (Persistensi State & Instance)

> **Catatan:** Fitur ini sengaja ditunda karena kompleksitasnya sangat tinggi dan manfaat tambahannya bersifat inkremental di atas Prioritas 1. Fase 1 (restart tanpa reload Pyodide) sudah menyelesaikan ~90% masalah kecepatan iterasi.

### 4.1 Sasaran
Mempertahankan `_state` dan *instance* komponen yang tidak berubah saat hot reload, sehingga:
- Form yang sedang diisi tidak ter-reset.
- Posisi scroll daftar panjang tidak hilang.
- Data yang sudah di-fetch tidak perlu diambil ulang.

### 4.2 Strategi: `importlib.reload()` + Migrasi Instance

```python
import importlib

def hot_reload_module(module_name: str):
    mod = sys.modules[module_name]
    importlib.reload(mod)

    # Setelah reload, kelas baru sudah ter-load ke memori.
    # Migrasi instance lama ke kelas baru:
    for key, instance in app.component_map.items():
        OldClass = type(instance)
        NewClass = getattr(mod, OldClass.__name__, None)

        if NewClass is None or NewClass is OldClass:
            continue  # Tidak berubah atau sudah dihapus

        # Transfer state
        instance.__class__ = NewClass  # "Hot-swap" kelas
        # instance._state tetap utuh karena dict Python tidak peduli kelas
```

### 4.3 Batasan & Risiko
- **Perubahan `__init__`:** Jika developer mengubah inisialisasi `_state` (menambah/menghapus field), instance lama akan memiliki state yang *stale* atau *missing*. Solusi: deteksi perubahan *signature* `__init__` dan lakukan *full remount* untuk komponen tersebut.
- **Perubahan Struktur Tree:** Jika developer mengubah `render()` sehingga menambah/menghapus child component, `component_map` akan *stale*. Solusi: lakukan *full re-expand* dari komponen yang berubah ke bawah.
- **Circular Import:** `importlib.reload()` tidak aman terhadap sirkular import. Perlu urutan reload yang deterministik berdasarkan graf dependensi.

### 4.4 Alternatif Lebih Sederhana: Persistensi State Berbasis Snapshot
Alih-alih mempertahankan instance, kita bisa:
1. Sebelum restart, *serialize* semua `_state` dari `component_map` ke dictionary `{component_key: state_dict}`.
2. Restart penuh (seperti Prioritas 1).
3. Setelah *mount* ulang, *restore* `_state` dari snapshot ke instance baru yang memiliki key yang sama.

Ini jauh lebih sederhana dan aman, meskipun agak lebih lambat karena seluruh tree tetap di-*re-expand*.

---

## 5. Prioritas Rendah: Fitur DX Tambahan

### 5.1 Error Overlay
Saat terjadi error Python di browser, alih-alih hanya menampilkan di console, tampilkan *overlay* merah transparan di atas halaman aplikasi yang menunjukkan traceback lengkap. Overlay hilang otomatis saat file diperbaiki dan di-reload.

### 5.2 Indikator Status Reload
Menampilkan indikator visual kecil (misalnya titik kuning berkedip di pojok layar) saat proses reload sedang berjalan, berubah hijau jika sukses atau merah jika gagal.

### 5.3 CSS/HTML Hot Reload
Memperluas watcher dan SSE agar perubahan file `.css` dan `.html` juga memicu reload tanpa harus me-restart seluruh aplikasi Python. CSS bahkan bisa di-*inject* langsung tanpa restart sama sekali.
""", "toolAction": "Creating dev server specification document", "toolSummary": "Create DEV_SERVER.md spec"
