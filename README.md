# Metaphoto-AI

Tool untuk menganalisis foto menggunakan AI, mengganti nama berkas secara otomatis ramah SEO, dan menyisipkan metadata `Title` + `Keywords` ke dalam foto agar siap diunggah ke platform Microstock (seperti Adobe Stock atau Shutterstock).

## Cara Kerja (1:1 Berurutan)

Aplikasi memproses setiap berkas gambar (`.jpg`, `.jpeg`, `.png`, dll) di dalam folder `photos/` secara berurutan:
1. **Analisis Gambar (Tahap 1 - Vision)**: Gambar diecilkan secara dinamis (maksimal 512px) untuk meminimalkan beban RAM/VRAM GPU, lalu dianalisis menggunakan model Vision lokal (default: `moondream` atau `qwen2.5vl:3b` via Ollama) untuk mendeskripsikan isi gambar secara terstruktur.
2. **Optimasi SEO (Tahap 2 - Text)**: Menggunakan model **Gemini 3 Flash Preview** (via OpenRouter) untuk menyusun Judul SEO deskriptif dan menghasilkan tepat 45 Kata Kunci (Keywords) terurut berdasarkan popularitas pencarian.
3. **Penyisipan Metadata & Rename**:
   * Nama berkas diganti dengan Judul SEO yang telah disanitasi dari karakter ilegal.
   * Metadata `Title`, `Description/Caption`, dan `Keywords` ditulis langsung ke dalam berkas gambar ke seluruh tag standar (**EXIF, IPTC, dan XMP**) menggunakan `exiftool` agar kompatibel penuh dengan Shutterstock & Adobe Stock.
4. **Caching & Rekap**:
   * Menyimpan cache di `.metaphoto_cache.json` agar foto yang sudah terproses tidak dianalisis ulang jika script dijalankan kembali.
   * Menulis rekapitulasi data seluruh foto yang sukses diproses ke dalam folder `log/` dengan format JSON berurut waktu.

---

## Struktur Folder

```text
metaphoto/
├── main.py                 # Core engine (AI & Metadata Writer)
├── Dockerfile              # Docker recipe (berisi Python + exiftool + requests)
├── docker-compose.yml      # Konfigurasi container & integrasi jaringan Ollama
├── Makefile                # Shortcut perintah eksekusi
├── README.md
├── AGENTS.md               # Dokumentasi petunjuk untuk AI Agent pengembang
├── .env                    # Kunci API OpenRouter (diabaikan oleh git)
├── .metaphoto_cache.json   # Berkas cache pemrosesan (diabaikan oleh git)
├── log/                    # Folder log rekap metadata (diabaikan oleh git)
└── photos/                 # Folder foto input (berkas di dalamnya akan diproses langsung)
```

---

## Persiapan & Penggunaan

### 1. Prasyarat (Prerequisites)
1. Docker & Docker Compose terinstal di mesin Anda.
2. Server Ollama berjalan di mesin lokal (dalam kontainer bernama `ollama_server` pada jaringan `ollama_default`).
3. Model `moondream:latest` sudah terpasang di Ollama lokal Anda (`ollama pull moondream`).

### 2. Konfigurasi API Key
Buat berkas `.env` di root direktori proyek dan masukkan API Key OpenRouter Anda untuk model Gemini:
```env
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxx
```

### 3. Eksekusi Program
Letakkan foto-foto yang ingin diproses ke dalam folder `photos/`, lalu jalankan perintah:

```bash
make run
```
*(Perintah ini setara dengan menjalankan `docker compose up --build`)*

---

## Output

Setelah selesai, program akan:
1. Mengubah nama berkas asli di folder `photos/` menjadi nama ramah SEO (Contoh: `photos/beautiful-beach-sunset.jpg`).
2. Menyisipkan tag metadata **EXIF, IPTC, dan XMP** (`Title`, `Description/Caption`, dan `Keywords`) ke dalam foto.
3. Membuat berkas rekap JSON berurutan waktu di dalam folder `log/` (contoh: `log/metadata_20260707_121526.json`) yang berisi detail file asal/tujuan, judul, kata kunci, deskripsi, serta data hasil model vision (`vision_model`, `vision_raw`, `vision_detail`).
