import os
import re
import json
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OUTPUT_DIR = "src/content/post"

RSS_FEEDS = [
    "https://feeds.feedburner.com/TechCrunch",
    "https://www.theverge.com/rss/full.xml",
]

MAX_ITEMS = 3


# ── Utils ─────────────────────────────────────────────
def fetch_url(url):
    print(f"[fetch] {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def clean_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_rss_items(feed_url):
    try:
        raw = fetch_url(feed_url)
        root = ET.fromstring(raw)
        items = []

        for item in root.iter("item"):
            title = clean_html(item.findtext("title", ""))
            desc = clean_html(item.findtext("description", ""))
            link = item.findtext("link", "")

            if title and link:
                items.append({
                    "title": title,
                    "description": desc[:400],
                    "link": link
                })

        print(f"[rss] {feed_url} -> {len(items)} itens")
        return items

    except Exception as e:
        print(f"[erro RSS] {e}")
        return []


# ── Retry Gemini ──────────────────────────────────────
def call_gemini_with_retry(req, retries=3):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())

        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 5 * (attempt + 1)
                print(f"[429] Rate limit... retry em {wait}s")
                time.sleep(wait)
            else:
                raise e

    raise Exception("❌ Falhou após retries (429)")


# ── Gemini ────────────────────────────────────────────
def rewrite_with_gemini(items):
    if not GEMINI_API_KEY:
        raise Exception("❌ GEMINI_API_KEY não encontrada")

    print("[debug] API KEY OK")

    noticias = "\n\n".join([
        f"Título: {i['title']}\nResumo: {i['description']}\nLink: {i['link']}"
        for i in items
    ])

    prompt = f"""
Responda APENAS com JSON válido.

NÃO escreva texto antes ou depois.
NÃO use markdown fora do campo body.

Formato obrigatório:

{{
  "title": "...",
  "description": "...",
  "tags": ["tecnologia"],
  "body": "conteúdo em markdown"
}}

Regras:
- português brasileiro
- mínimo 800 palavras
- conteúdo denso
- múltiplas seções

NOTÍCIAS:
{noticias}
"""

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096,
            "topP": 0.9
        }
    }).encode("utf-8")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        data = call_gemini_with_retry(req)

        print("[debug] resposta recebida")

        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

        print("[debug] resposta bruta:")
        print(text[:500])

        # ── parse direto
        try:
            result = json.loads(text)
        except:
            # ── fallback robusto
            start = text.find("{")
            end = text.rfind("}")

            if start == -1 or end == -1:
                raise Exception("❌ Nenhum JSON encontrado")

            json_text = text[start:end+1]

            try:
                result = json.loads(json_text)
            except Exception as e:
                print(json_text[:1000])
                raise Exception(f"❌ JSON inválido: {e}")

        # ── validação
        if "body" not in result:
            raise Exception("❌ JSON sem body")

        if len(result["body"].split()) < 600:
            raise Exception("❌ Conteúdo muito curto")

        print("[gemini] sucesso real")
        return result

    except Exception as e:
        print(f"[ERRO GEMINI REAL] {e}")
        raise e


# ── Writer ────────────────────────────────────────────
def write_post(post):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    slug = "resumo-semanal-tech"

    tags = "\n".join(f'  - "{t}"' for t in post.get("tags", ["tecnologia"]))

    content = f"""---
title: "{post['title']}"
description: "{post['description']}"
tags:
{tags}
pubDate: {today}
---

{post['body']}
"""

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    path = f"{OUTPUT_DIR}/{today}-{slug}.md"

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[OK] arquivo criado: {path}")


# ── MAIN ─────────────────────────────────────────────
def main():
    print("🔍 buscando notícias")

    all_items = []

    for feed in RSS_FEEDS:
        all_items.extend(fetch_rss_items(feed))

    if not all_items:
        raise Exception("❌ Nenhuma notícia encontrada")

    items = all_items[:MAX_ITEMS]

    print(f"[usando] {len(items)} notícias")

    post = rewrite_with_gemini(items)

    write_post(post)

    print("✅ FINALIZADO COM SUCESSO")


if __name__ == "__main__":
    main()