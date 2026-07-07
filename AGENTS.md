# AI Developer Guide - Metaphoto-AI

This document serves as a handover and reference guide for AI agents working on the **metaphoto-ai** repository.

---

## 🚀 Current Architecture & Workflow

The project is simplified into a unified single-stage pipeline running inside a Docker container:

```text
Photos Folder (photos/) 
      ↓ (Scan JPG/JPEG/PNG)
main.py (Unified Metadata Engine)
      ↓ (Check .metaphoto_cache.json)
      ├─ Cache Hit  → Load metadata directly from cache
      └─ Cache Miss → AI Pipeline:
                         1. Tahap 1 (Vision): local 'moondream:latest' via Ollama (ollama_server:11434)
                         2. Tahap 2 (Text/SEO): 'google/gemini-3-flash-preview' via OpenRouter
                         3. Rename photo to sanitized SEO title
                         4. Write EXIF/IPTC/XMP tags (Title, Description & Keywords) using exiftool
                         5. Save result to cache
      ↓
log/metadata_YYYYMMDD_HHMMSS.json (Timestamped Summary)
```

---

## 🛠️ Configuration & Setup

### Environment Variables
The application receives configurations through the environment:
* `VISION_API_BASE_URL` (default: `http://ollama_server:11434/v1/chat/completions`)
* `VISION_MODEL` (default: `moondream`)
* `TEXT_API_BASE_URL` (default: `https://openrouter.ai/api/v1/chat/completions`)
* `TEXT_MODEL` (default: `google/gemini-3-flash-preview`)
* `OPENROUTER_API_KEY` (loaded from `.env`)

### Docker Networking
* The container runs on the **`ollama_default`** external network.
* This allows the app to communicate with the host's Ollama instance at the hostname `ollama_server` on port `11434`.
* Any Docker Compose setup must define this network as external.

---

## 💾 Caching & Rename Logic (Key Design Decision)

To prevent re-running expensive or slow AI inference, a cache file `.metaphoto_cache.json` is used.
* **Problem**: In the original app, files were renamed *after* metadata generation, which changed their path. If cached by their original path, next runs would see the renamed file as new (cache miss) and re-process it.
* **Solution**: 
  1. The cache stores file paths as relative paths (e.g. `photos/my-renamed-title.jpg`).
  2. When a new file is processed and successfully renamed, it is stored in the cache using its **new path**.
  3. The next execution sees the already-renamed file, finds it in the cache, and skips it safely.

---

## 📝 Roadmap & Future Ideas

Here are potential improvements you can work on:

1. **Export to CSV**:
   * Platforms like Shutterstock and Adobe Stock support bulk metadata upload via CSV.
   * Add a function to generate a standard microstock CSV (`filename, title, description, keywords`) alongside the generated JSON log file for easy uploading.
2. **Support Local Text/SEO Models**:
   * Add support for utilizing local text models (like `qwen2.5:latest`) for Phase 2 instead of OpenRouter, allowing 100% offline usage.
3. **Web User Interface (WebUI)**:
   * Build a simple web frontend using React or vanilla HTML/JS to view processed photos, edit generated titles/keywords, and trigger executions.
4. **Custom Vision Templates**:
   * Optimize `VISION_SYSTEM_PROMPT` for other vision models (e.g., Llama 3.2 Vision, Qwen2.5-VL) to get richer or faster descriptions.
