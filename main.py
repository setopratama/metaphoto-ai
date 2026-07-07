import os
import sys
import random
import subprocess
import re
import glob

ILLEGAL_CHARS = re.compile(r'[\x00-\x1f/\\:*?"<>|]')
RESERVED_WIN = {
    name.upper() for name in
    "CON PRN AUX NUL COM1 COM2 COM3 COM4 COM5 COM6 COM7 COM8 COM9 "
    "LPT1 LPT2 LPT3 LPT4 LPT5 LPT6 LPT7 LPT8 LPT9".split()
}


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


def read_lines(path):
    with open(path, 'r', encoding='utf-8') as f:
        return [line.rstrip('\n\r') for line in f]


def read_keywords(path):
    lines = read_lines(path)
    return [[kw.strip() for kw in line.split(',') if kw.strip()] for line in lines]


def write_metadata(filepath, title, keywords):
    cmd = ['exiftool', '-overwrite_original']
    cmd.extend([f'-Title={title}'])
    cmd.extend([f'-ImageDescription={title}'])
    for kw in keywords:
        cmd.extend([f'-Keywords={kw}'])
    cmd.append(filepath)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stderr


def check_exiftool():
    result = subprocess.run(['which', 'exiftool'], capture_output=True, text=True)
    if result.returncode != 0:
        print("ERROR: exiftool tidak ditemukan di PATH")
        sys.exit(1)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    check_exiftool()

    title_file = 'title.txt'
    keyword_file = 'keyword.txt'

    if not os.path.exists(title_file):
        print(f"ERROR: {title_file} tidak ditemukan")
        sys.exit(1)
    if not os.path.exists(keyword_file):
        print(f"ERROR: {keyword_file} tidak ditemukan")
        sys.exit(1)

    titles = read_lines(title_file)
    keywords = read_keywords(keyword_file)

    titles = [t for t in titles if t]
    keywords = [k for k in keywords if k]

    if not titles:
        print("ERROR: title.txt kosong")
        sys.exit(1)
    if not keywords:
        print("ERROR: keyword.txt kosong")
        sys.exit(1)

    photos_dir = os.path.join(script_dir, 'photos')
    if not os.path.isdir(photos_dir):
        print(f"ERROR: Folder 'photos' tidak ditemukan di {script_dir}")
        sys.exit(1)

    files = [f for f in glob.glob(os.path.join(photos_dir, '*.jpg'))
             + glob.glob(os.path.join(photos_dir, '*.jpeg'))
             + glob.glob(os.path.join(photos_dir, '*.png'))
             + glob.glob(os.path.join(photos_dir, '*.JPG'))
             + glob.glob(os.path.join(photos_dir, '*.JPEG'))
             + glob.glob(os.path.join(photos_dir, '*.PNG'))
             ]

    files = [os.path.basename(f) for f in files]

    if not files:
        print("ERROR: Tidak ada file .jpg/.png/.jpeg di folder photos/")
        sys.exit(1)

    random.shuffle(files)
    random.shuffle(titles)
    random.shuffle(keywords)

    used_names = set()
    success = 0
    fail = 0
    logs = []

    for i, filepath in enumerate(files):
        title = titles[i % len(titles)]
        kws = keywords[i % len(keywords)]

        ext = os.path.splitext(filepath)[1].lower()
        safe_base = sanitize_filename(title)
        if safe_base is None:
            logs.append(f"SKIP: {filepath} -> title kosong setelah sanitasi: '{title}'")
            fail += 1
            continue

        new_name = safe_base + ext
        dedup_count = 2
        orig_base = safe_base
        while new_name.lower() in used_names or os.path.exists(os.path.join(photos_dir, new_name)):
            safe_base = f"{orig_base}_{dedup_count}"
            new_name = safe_base + ext
            dedup_count += 1

        old_path = os.path.join(photos_dir, filepath)
        new_path = os.path.join(photos_dir, new_name)

        try:
            os.rename(old_path, new_path)
        except OSError as e:
            logs.append(f"RENAME FAIL: {filepath} -> {new_name}: {e}")
            fail += 1
            continue

        used_names.add(new_name.lower())

        ok, err = write_metadata(new_path, title, kws)
        if ok:
            logs.append(f"OK: {filepath} -> {new_name} | Title: {title} | Keywords: {','.join(kws)}")
            success += 1
        else:
            logs.append(f"META FAIL: {new_name} (exiftool): {err}")
            fail += 1

    print("\n=== HASIL ===")
    print(f"Sukses: {success}")
    print(f"Gagal: {fail}")
    print("\n--- Detail ---")
    for line in logs:
        print(line)


if __name__ == '__main__':
    main()
