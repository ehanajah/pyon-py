# Spesifikasi Ekstensi Modul HTTP Pyon-Py

Dokumen ini mendokumentasikan rencana fitur tingkat lanjut dan ekstensi masa depan untuk modul `pyon.http`. Fitur-fitur ini sengaja ditunda agar prioritas pengembangan framework saat ini bisa terfokus pada fitur inti SPA (seperti SPA Router).

## 1. Pembatalan Request (AbortController)
Saat komponen UI dihapus (*unmount*) namun permintaan HTTP masih berjalan di latar belakang (misalnya koneksi sedang lambat), balasan yang datang akan mencoba merender ulang komponen yang sudah tidak ada. Hal ini berpotensi membocorkan memori atau meletupkan `Exception`.

**Rencana Implementasi:**
- Integrasikan `AbortController` milik Javascript ke pemanggilan `pyfetch`.
- Di dalam kelas `Resource`, simpan referensi kontrol pembatalan.
- Jika metode siklus hidup `on_unmount` terpanggil pada komponen yang mengikat *resource* tersebut, `Resource` harus memanggil `controller.abort()`.
- Tangkap galat `AbortError` agar tidak mengotori *console* dan tidak merender ulang UI yang sudah mati.

## 2. Server-Sent Events (SSE)
Banyak aplikasi membutuhkan aliran data tunggal secara berkelanjutan tanpa melakukan siklus respons berulang (seperti papan nilai live, indikator perdagangan saham). 

**Rencana Implementasi:**
- Buat sub-modul `pyon/http/sse.py`.
- Gunakan konstruktor asli Javascript `new EventSource(url)`.
- Rancang kelas reaktif `SSEResource` yang menyerupai `Resource`, tetapi status `self.data` terus diperbarui seiring berjalannya `onmessage` dari `EventSource`.

## 3. WebSockets
Protokol dua arah untuk aplikasi waktu-nyata yang jauh lebih interaktif (misalnya obrolan (*chat*) atau gim multipemain).

**Rencana Implementasi:**
- Buat sub-modul `pyon/http/ws.py`.
- Rancang kelas `WebSocketClient` yang membungkus antarmuka `WebSocket` browser asli.
- Sediakan metode kirim (*send*) dan kaitan kejadian (*event hooks*) untuk `on_open`, `on_message`, `on_error`, dan `on_close`.
- Hubungkan penerima *message* langsung dengan pengaktif *re-render* di komponen jika diperlukan.

## 4. Sistem Client Session Terpusat
Saat ini, setiap memanggil `get()` atau `post()`, kita harus memasukkan seluruh konfigurasi dasar (seperti `base_url` atau *header* otentikasi) secara terus-menerus.

**Rencana Implementasi:**
- Rancang kelas `HTTPClient` yang serupa dengan `httpx.Client`.
- Kelas ini menyimpan `base_url`, `default_headers`, `default_timeout`, dan `interceptors`.
- Alih-alih memanggil `from pyon.http import get`, pengembang akan menginstansiasi *client* sekali (kemungkinan dimasukkan ke dalam *Context* App):
  ```python
  client = HTTPClient(base_url="https://api.example.com", headers={"Authorization": "Bearer XYZ"})
  await client.get("/users")
  ```
