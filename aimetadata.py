"""
generate_metaphoto_metadata.py
--------------------------------
Generator 2-TAHAP untuk https://github.com/setopratama/metaphoto-ai

TAHAP 1 (VISION MODEL - lokal, moondream via Ollama):
    Model kecil & cepat (1.6B), diminta isi TEMPLATE terstruktur
    (Subject/Action/Setting/Colors/Mood/Style) -- bukan deskripsi bebas,
    karena moondream lebih jago menjawab pertanyaan singkat & literal
    daripada mengarang deskripsi panjang sendiri.

TAHAP 2 (TEXT MODEL - cloud, model lebih kuat, contoh: Gemini 3 Flash Preview):
    Menerima catatan terstruktur dari Tahap 1, lalu menyusun Title SEO +
    45 Keyword mengikuti strategi "keyword populer dulu, niche belakangan"
    (broad/high-search-volume di 5-10 keyword pertama, spesifik di sisanya),
    sesuai kaidah Adobe Stock & Shutterstock. Karena tahap ini TEXT-ONLY
    (tanpa gambar), biayanya sangat kecil meski pakai model yang lebih kuat/mahal --
    justru di sinilah kualitas title/keyword paling menentukan, jadi tidak
    perlu irit di tahap ini.

Kenapa dipisah begini:
    - Model vision kecil kalau disuruh sekaligus deskripsi + mikir SEO +
      susun keyword terurut relevansi dalam satu prompt -> hasil berantakan.
    - Dipecah dua tahap: Tahap 1 fokus "apa isi gambar", Tahap 2 fokus
      "bagaimana menjualnya" -- tiap model kerja sesuai kekuatannya masing-masing.

Output:
    title.txt              -> 1 baris = 1 judul foto
    keyword.txt             -> 1 baris = keyword dipisah koma, untuk foto yg sama
    deskripsi_mentah.txt    -> (debug) catatan terstruktur dari Tahap 1, urutan sama

PENTING soal urutan file:
    main.py di metaphoto-ai melakukan random.shuffle() pada files, titles,
    DAN keywords secara terpisah sebelum dipasangkan. Jadi urutan baris di
    title.txt/keyword.txt TIDAK dijamin nempel ke foto yang benar setelah
    main.py dijalankan -- itu murni desain/bug di main.py, bukan di script
    ini. Kalau butuh 1:1 akurat sesuai isi foto, main.py perlu dipatch
    (hapus 3 baris random.shuffle) sebelum dijalankan.

Setup:
    pip install requests

    # Tahap 1 - vision, default: moondream via Ollama lokal
    #   ollama pull moondream
    export VISION_API_BASE_URL="http://localhost:11434/v1/chat/completions"
    export VISION_MODEL="moondream"

    # Tahap 2 - text (SEO), default: model lebih kuat via OpenRouter
    export TEXT_API_BASE_URL="https://openrouter.ai/api/v1/chat/completions"
    export TEXT_MODEL="google/gemini-3-flash-preview"
    export OPENROUTER_API_KEY="sk-or-xxxx"

    # ATAU kalau mau tahap 2 juga lokal (butuh model text lebih besar dari moondream,
    # misal qwen2.5:7b-instruct, supaya kualitas SEO-nya tetap layak):
    export TEXT_API_BASE_URL="http://localhost:11434/v1/chat/completions"
    export TEXT_MODEL="qwen2.5:7b-instruct"
    # (OPENROUTER_API_KEY tidak perlu diisi kalau endpoint-nya localhost)

Jalankan (dari folder yang sama dengan main.py metaphoto-ai, foto ada di photos/):
    python generate_metaphoto_metadata.py
    python main.py     # atau: make run
"""

import os
import sys
import json
import time
import base64
import mimetypes
import requests

# ---------- Konfigurasi ----------
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

VISION_API_URL = os.environ.get("VISION_API_BASE_URL", "http://localhost:11434/v1/chat/completions")
VISION_MODEL = os.environ.get("VISION_MODEL", "moondream")

TEXT_API_URL = os.environ.get("TEXT_API_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
TEXT_MODEL = os.environ.get("TEXT_MODEL", "google/gemini-3-flash-preview")

PHOTOS_DIR = "photos"
TITLE_FILE = "title.txt"
KEYWORD_FILE = "keyword.txt"
DESC_DEBUG_FILE = "deskripsi_mentah.txt"
CACHE_FILE = ".metaphoto_cache.json"

MAX_KEYWORDS = 45
REQUEST_DELAY_SEC = 0.5
MAX_RETRIES = 3

# ---------- Prompt Tahap 1: Vision -> deskripsi terstruktur ----------
# Moondream itu model kecil (1.6B) yang paling jago menjawab pertanyaan singkat
# dan literal. Kalau diminta "deskripsikan gambar ini secara bebas", hasilnya
# sering terlalu pendek/generik. Jadi di sini kita minta dia isi TEMPLATE
# terstruktur (mirip fill-in-the-blank) -- ini masih dalam kemampuannya,
# tapi hasilnya jauh lebih kaya sebagai bahan mentah untuk Tahap 2.
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
    """TAHAP 1: vision model -> deskripsi polos (bukan JSON, teks biasa)."""
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
    """TAHAP 2: text model -> title + keywords (JSON) dari deskripsi polos."""
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
    return sorted(files)  # kita urutkan biar deterministic di sisi kita


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
    results = []  # list of dict {desc, title, keywords} sejajar dengan `files`

    for i, path in enumerate(files, start=1):
        rel = os.path.relpath(path, folder)
        if rel in cache:
            print(f"[{i}/{len(files)}] [CACHE] {rel}")
            results.append(cache[rel])
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
        cache[rel] = entry
        results.append(entry)
        save_cache(cache)
        time.sleep(REQUEST_DELAY_SEC)

    with open(os.path.join(folder, TITLE_FILE), "w", encoding="utf-8") as f:
        for r in results:
            f.write((r["title"] or "untitled-image") + "\n")

    with open(os.path.join(folder, KEYWORD_FILE), "w", encoding="utf-8") as f:
        for r in results:
            f.write(", ".join(r["keywords"]) + "\n")

    with open(os.path.join(folder, DESC_DEBUG_FILE), "w", encoding="utf-8") as f:
        for r in results:
            f.write((r["desc"] or "") + "\n")

    failed = sum(1 for r in results if not r["title"])
    print(f"\n[SUCCESS] {TITLE_FILE}, {KEYWORD_FILE}, dan {DESC_DEBUG_FILE} dibuat untuk {len(results)} foto.")
    if failed:
        print(f"[WARN] {failed} foto gagal diproses penuh, cek '{DESC_DEBUG_FILE}' untuk debug.")
    print("\n!!! INGAT: main.py metaphoto-ai men-shuffle files/title/keyword secara acak.")
    print("    Kalau mau pasangan title-keyword TETAP sesuai isi foto masing-masing,")
    print("    hapus 3 baris random.shuffle(...) di main.py sebelum dijalankan.")
    print("\nLanjutkan dengan: python main.py")


if __name__ == "__main__":
    main()
