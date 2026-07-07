# Metaphoto

Tool buat rename file foto dan isi metadata `Title` + `Keywords` dari file text.

## Cara kerja

- `title.txt` = 1 baris 1 judul foto
- `keyword.txt` = 1 baris 1 daftar keyword untuk 1 foto
- Semua file `.jpg`, `.jpeg`, dan `.png` dalam folder `photos/` akan diproses
- File akan diacak pasang ke baris title dan keyword
- Nama file hasil rename memakai title mentah yang sudah dibersihkan dari karakter ilegal
- Kalau nama duplikat, file akan diberi suffix angka: `_2`, `_3`, dst
- Metadata `Title` tetap memakai title asli tanpa suffix

## Struktur folder

```text
metaphoto/
├── main.py
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── title.txt
├── keyword.txt
├── README.md
└── photos/
    ├── foto1.jpg
    ├── foto2.png
    └── ...
```

## Format input

### `title.txt`

```text
Sunset Beach
Mountain View
City Skyline
```

### `keyword.txt`

```text
sunset, beach, ocean, horizon
mountain, nature, landscape, sky
city, skyline, building, urban
```

## Jalankan

Pastikan Docker dan Docker Compose sudah terpasang, lalu:

```bash
make run
```

## Output

Script akan:

- rename file foto
- isi metadata `Title`
- isi metadata `Keywords`
- tampilkan log sukses/gagal per file

## Catatan

- Kalau jumlah foto dan jumlah baris tidak sama, script akan memakai pola ulang dari atas.
- Jika title setelah sanitasi kosong, file itu akan dilewati.
- Proses ini mengubah file asli di folder kerja.
