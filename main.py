"""
main.py
--------------------------------
Generator 2-TAHAP & Writer Metadata untuk https://github.com/setopratama/metaphoto-ai

TAHAP 1 (VISION MODEL - lokal, moondream via Ollama):
    Model kecil & cepat (1.6B), diminta isi TEMPLATE terstruktur
    (Subject/Action/Setting/Colors/Mood/Style).

TAHAP 2 (TEXT MODEL - cloud, model lebih kuat, contoh: Gemini 3 Flash Preview):
    Menerima catatan terstruktur dari Tahap 1, lalu menyusun Title SEO +
    45 Keyword mengikuti strategi "keyword populer dulu, niche belakangan".

TAHAP 3 (WRITER & RENAME):
    Mengubah nama berkas gambar sesuai dengan judul yang disanitasi,
    lalu menuliskan tag Title & Keywords langsung ke berkas menggunakan exiftool.
    Hubungan antara gambar dan metadata dijamin 1:1 (tidak diacak).

Setup:
    pip install requests
"""

import os
import sys
import json
import time
import base64
import mimetypes
import requests
import subprocess
import re

# ---------- Konfigurasi ----------
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

VISION_API_URL = os.environ.get("VISION_API_BASE_URL", "http://localhost:11434/v1/chat/completions")
VISION_MODEL = os.environ.get("VISION_MODEL", "moondream")

TEXT_API_URL = os.environ.get("TEXT_API_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
TEXT_MODEL = os.environ.get("TEXT_MODEL", "google/gemini-3-flash-preview")

PHOTOS_DIR = "photos"
LOG_DIR = "LOG"
CACHE_FILE = ".metaphoto_cache.json"

MAX_KEYWORDS = 45
REQUEST_DELAY_SEC = 0.5
MAX_RETRIES = 3

ILLEGAL_CHARS = re.compile(r'[\x00-\x1f/\\:*?"<>|]')
RESERVED_WIN = {
    name.upper() for name in
    "CON PRN AUX NUL COM1 COM2 COM3 COM4 COM5 COM6 COM7 COM8 COM9 "
    "LPT1 LPT2 LPT3 LPT4 LPT5 LPT6 LPT7 LPT8 LPT9".split()
}

# ---------- Prompt Tahap 1: Vision -> deskripsi terstruktur ----------
VISION_SYSTEM_PROMPT = """You describe images factually and literally. Answer ONLY in this exact template,
one line per field, in English. Keep each answer short and concrete (max 1 short sentence per field).
Do not add any other text, explanation, or formatting.

Subject: <main subject(s) in the image, what/who they are>
Action: <what is happening / what the subject is doing, or "static/still" if nothing>
Setting: <location, background, environment>
Colors: <2-4 dominant colors>
Mood: <overall mood/feeling, e.g. calm, energetic, professional, cozy>
Style: <photo, illustration, vector, 3d render, flat lay, etc — only if clearly identifiable>"""

# ---------- Prompt Tahap 2: deskripsi -> title + keywords SEO ----------
TEXT_SYSTEM_PROMPT = f"""Anda adalah asisten SEO metadata untuk foto/ilustrasi yang dijual di
Adobe Stock dan Shutterstock. Anda akan menerima CATATAN TERSTRUKTUR tentang sebuah gambar
(Subject/Action/Setting/Colors/Mood/Style, bukan gambarnya langsung, dan mungkin agak singkat
karena berasal dari model vision kecil). Tugas Anda: rangkai jadi Title + Keywords yang matang,
dengan menambahkan konteks/sinonim/istilah pencarian yang wajar berdasarkan catatan tersebut.

STRATEGI KEYWORD "POPULER" (penting):
- Urutkan keyword dari yang PALING SERING DICARI ke yang paling niche/spesifik.
- 5-10 keyword pertama harus istilah BROAD & bervolume pencarian tinggi (kategori umum:
  contoh "business", "nature", "technology", "family", "food" -- bukan istilah spesifik dulu).
- Sisanya baru istilah lebih spesifik/deskriptif (kombinasi 2-3 kata, konsep abstrak, use-case).
- Selipkan sinonim yang lazim dicari pembeli stock (contoh: "laptop" DAN "computer" keduanya
  valid kalau relevan, karena pembeli mencari dengan kata berbeda-beda untuk hal yang sama).

ATURAN TITLE:
- Bahasa Inggris, natural, deskriptif, seperti kalimat singkat (bukan tumpukan keyword).
- Sebutkan subjek utama, aksi/kondisi, dan konteks/setting secara jelas di awal kalimat.
- Panjang ideal 60-100 karakter (jangan lebih dari 150 karakter).
- JANGAN pakai huruf kapital semua (ALL CAPS).
- JANGAN sertakan merek dagang, nama brand, logo, karakter berhak cipta, nama selebriti.
- JANGAN sertakan info kamera/teknis.
- JANGAN pakai karakter ilegal untuk nama file: < > : " / \\ | ? *

ATURAN KEYWORDS:
- Hasilkan tepat {MAX_KEYWORDS} kata kunci, diurutkan sesuai strategi "populer" di atas.
- Campuran: subjek utama, aksi, emosi/mood, warna dominan, setting/lokasi, konsep abstrak
  (contoh: "success", "teamwork", "sustainability"), gaya visual (photo/illustration/
  3d render/vector), komposisi (copy space, close-up, top view, isolated on white),
  dan use-case bisnis yang relevan jika sesuai (contoh: technology, healthcare, finance).
- Kata kunci berupa kata tunggal atau frasa pendek (maksimal 2-3 kata), BUKAN kalimat.
- Tidak boleh ada duplikat atau sinonim yang diulang-ulang berlebihan (keyword stuffing).
- JANGAN sertakan nama brand, logo, nama orang/selebriti, atau karakter berhak cipta.
- Semua keyword dalam Bahasa Inggris.

FORMAT OUTPUT:
Balas HANYA dengan JSON valid, tanpa markdown, tanpa penjelasan tambahan, persis format ini:
{{"title": "...", "keywords": ["keyword1", "keyword2", "..."]}}
"""

def check_exiftool():
    result = subprocess.run(['which', 'exiftool'], capture_output=True, text=True)
    if result.returncode != 0:
        print("[FAIL] exiftool tidak ditemukan di PATH")
        sys.exit(1)

def sanitize_filename(name):
    name = ILLEGAL_CHARS.sub('', name)
    name = name.strip()
    name = re.sub(r' +', ' ', name)
    if not name:
        return None
    base, ext = os.path.splitext(name)
    if base.upper() in RESERVED_WIN or base.upper().startswith('CON'):
        base = base + '_'
    if base.endswith('.') or base.endswith(' '):
        base = base.rstrip('. ') + '_'
    return base

def write_metadata(filepath, title, keywords):
    cmd = ['exiftool', '-overwrite_original']
    cmd.extend([f'-Title={title}'])
    cmd.extend([f'-ImageDescription={title}'])
    for kw in keywords:
        cmd.extend([f'-Keywords={kw}'])
    cmd.append(filepath)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stderr

def encode_image_data_url(path):
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def call_model(api_url, model, messages, api_key="", max_tokens=800, temperature=0.4):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = requests.post(api_url, headers=headers, json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def describe_image(path, attempt=1):
    try:
        data_url = encode_image_data_url(path)
        messages = [
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Fill in the template for this image."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ]
        text = call_model(
            VISION_API_URL, VISION_MODEL, messages,
            api_key=OPENROUTER_API_KEY if "openrouter.ai" in VISION_API_URL else "",
            max_tokens=300, temperature=0.3,
        )
        text = text.strip()
        if not text:
            raise ValueError("Deskripsi kosong")
        return text
    except Exception as e:
        if attempt < MAX_RETRIES:
            time.sleep(2 * attempt)
            return describe_image(path, attempt + 1)
        print(f"    [WARN] Tahap 1 (vision) gagal: {e}")
        return ""

def parse_json_reply(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    text = text.strip()
    data = json.loads(text)
    title = str(data["title"]).strip()
    keywords = [str(k).strip() for k in data.get("keywords", []) if str(k).strip()]
    return title, keywords

def generate_seo_metadata(description, attempt=1):
    try:
        messages = [
            {"role": "system", "content": TEXT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Deskripsi gambar:\n{description}"},
        ]
        raw = call_model(
            TEXT_API_URL, TEXT_MODEL, messages,
            api_key=OPENROUTER_API_KEY if "openrouter.ai" in TEXT_API_URL else "",
            max_tokens=800, temperature=0.5,
        )
        title, keywords = parse_json_reply(raw)
        if not title or not keywords:
            raise ValueError("Title/keywords kosong")
        return title, keywords[:MAX_KEYWORDS]
    except Exception as e:
        if attempt < MAX_RETRIES:
            time.sleep(2 * attempt)
            return generate_seo_metadata(description, attempt + 1)
        print(f"    [WARN] Tahap 2 (text/SEO) gagal: {e}")
        return "", []

def scan_photos(folder):
    exts = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")
    files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(exts)]
    return sorted(files)

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def main():
    folder = os.getcwd()
    photos_dir = os.path.join(folder, PHOTOS_DIR)
    if not os.path.exists(photos_dir):
        print(f"[FAIL] Folder '{PHOTOS_DIR}/' tidak ditemukan di {folder}.")
        sys.exit(1)

    check_exiftool()

    files = scan_photos(photos_dir)
    if not files:
        print(f"[FAIL] Tidak ada file JPG/JPEG/PNG di '{PHOTOS_DIR}/'.")
        sys.exit(1)

    is_text_local = "localhost" in TEXT_API_URL or "127.0.0.1" in TEXT_API_URL
    if not OPENROUTER_API_KEY and not is_text_local and "openrouter.ai" in TEXT_API_URL:
        print("[FAIL] TEXT_API_BASE_URL mengarah ke OpenRouter tapi OPENROUTER_API_KEY belum diset.")
        sys.exit(1)

    print(f"Ditemukan {len(files)} foto.")
    print(f"Tahap 1 (vision) : {VISION_MODEL} @ {VISION_API_URL}")
    print(f"Tahap 2 (SEO)    : {TEXT_MODEL} @ {TEXT_API_URL}\n")

    cache = load_cache()
    used_names = {os.path.basename(f).lower() for f in files}
    results = []

    for i, path in enumerate(files, start=1):
        rel = os.path.relpath(path, folder)
        if rel in cache:
            print(f"[{i}/{len(files)}] [CACHE] {rel}")
            entry = cache[rel]
            results.append({
                "original_file": rel,
                "renamed_file": rel,
                "title": entry.get("title", ""),
                "keywords": entry.get("keywords", []),
                "description": entry.get("desc", "")
            })
            continue

        print(f"[{i}/{len(files)}] {rel}")
        desc = describe_image(path)
        print(f"    Deskripsi: {desc[:90]}{'...' if len(desc) > 90 else ''}")

        title, keywords = ("", [])
        if desc:
            title, keywords = generate_seo_metadata(desc)
            if title:
                print(f"    Title    : {title}")

        entry = {"desc": desc, "title": title, "keywords": keywords}
        
        final_rel = rel
        if title:
            ext = os.path.splitext(path)[1].lower()
            safe_base = sanitize_filename(title)
            if safe_base:
                new_name = safe_base + ext
                dedup_count = 2
                orig_base = safe_base
                while new_name.lower() in used_names or os.path.exists(os.path.join(photos_dir, new_name)):
                    safe_base = f"{orig_base}_{dedup_count}"
                    new_name = safe_base + ext
                    dedup_count += 1
                
                new_path = os.path.join(photos_dir, new_name)
                try:
                    os.rename(path, new_path)
                    used_names.add(new_name.lower())
                    final_rel = os.path.relpath(new_path, folder)
                    
                    ok, err = write_metadata(new_path, title, keywords)
                    if ok:
                        print(f"    [OK] Ganti nama & tulis metadata: {rel} -> {final_rel}")
                        cache[final_rel] = entry
                    else:
                        print(f"    [WARN] Gagal menulis metadata exiftool: {err}")
                        cache[final_rel] = entry
                except OSError as e:
                    print(f"    [WARN] Gagal mengganti nama berkas: {e}")
                    cache[rel] = entry
            else:
                print(f"    [WARN] Judul hasil sanitasi kosong untuk: {title}")
                cache[rel] = entry
        else:
            cache[rel] = entry

        results.append({
            "original_file": rel,
            "renamed_file": final_rel,
            "title": title,
            "keywords": keywords,
            "description": desc
        })
        save_cache(cache)
        time.sleep(REQUEST_DELAY_SEC)

    # Buat folder LOG jika belum ada
    log_dir_path = os.path.join(folder, LOG_DIR)
    os.makedirs(log_dir_path, exist_ok=True)

    # Format file JSON dengan tanggal dan detik (misal: metadata_20260707_121526.json)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    metadata_filename = f"metadata_{timestamp}.json"
    metadata_filepath = os.path.join(log_dir_path, metadata_filename)

    with open(metadata_filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    failed = sum(1 for r in results if not r["title"])
    print(f"\n[SUCCESS] Proses selesai. Rekap tersimpan di '{LOG_DIR}/{metadata_filename}'.")
    if failed:
        print(f"[WARN] {failed} foto gagal diproses penuh, silakan periksa file log/cache.")


if __name__ == "__main__":
    main()
