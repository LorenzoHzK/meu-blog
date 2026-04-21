import os
import re
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OUTPUT_DIR = "src/content/post"

RSS_FEEDS = [
    "https://feeds.feedburner.com/TechCrunch",
    "https://www.theverge.com/rss/index.xml",
]

MAX_POSTS = 1


# ── Utils ─────────────────────────────────────────────
def fetch_url(url):
    print(f"[fetch] {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_rss_items(feed_url, limit=3):
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

            if len(items) >= limit:
                break

        print(f"[rss] {feed_url} -> {len(items)} itens")
        return items

    except Exception as e:
        print(f"[erro RSS] {e}")
        return []


def rewrite_with_gemini(title, description, link):
    if not GEMINI_API_KEY:
        print("[erro] GEMINI_API_KEY não encontrada")
        return None

    prompt = f"""
Você é um desenvolvedor brasileiro escrevendo um blog pessoal.

Escreva um post em primeira pessoa, estilo experiência pessoal.

REGRAS:
- português brasileiro
- sem HTML
- usar markdown (##)
- entre 400 e 800 palavras

DADOS:
Título: {title}
Resumo: {description}
Link: {link}

Responda JSON:
{{
  "title": "",
  "description": "",
  "tags": [],
  "body": ""
}}
"""

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}]
    }).encode("utf-8")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        text = re.sub(r"```json|```", "", text).strip()

        result = json.loads(text)
        print("[gemini] sucesso")
        return result

    except Exception as e:
        print(f"[erro Gemini] {e}")
        return None


def fallback_post(item):
    print("[fallback] usando fallback")

    return {
        "title": item["title"],
        "description": item["description"][:120],
        "tags": ["tecnologia"],
        "body": f"""### Minha visão sobre isso

Vi recentemente essa notícia:

**{item['title']}**

{item['description']}

Confesso que achei interessante, principalmente porque esse tipo de coisa mostra como a tecnologia está evoluindo rápido.

Ainda não é algo que eu use diretamente no dia a dia, mas dá pra ver que isso pode impactar bastante coisa no futuro.

Fonte: {item['link']}
"""
    }


def safe(text):
    return str(text).replace('"', '\\"').replace("\n", " ").strip()


def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:60]


def write_post(post):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    title = safe(post["title"])
    description = safe(post["description"])
    slug = slugify(title)

    tags = "\n".join(f'  - "{safe(t)}"' for t in post.get("tags", ["tecnologia"]))

    content = f"""---
title: "{title}"
description: "{description}"
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

    print(f"[OK] post criado: {path}")


# ── MAIN ─────────────────────────────────────────────
def main():
    print("🔍 Buscando notícias...")

    all_items = []

    for feed in RSS_FEEDS:
        items = fetch_rss_items(feed)
        all_items.extend(items)

    print(f"[total] {len(all_items)} itens encontrados")

    if not all_items:
        print("[erro] nenhum item encontrado")
        return

    item = all_items[0]
    print(f"[usando] {item['title']}")

    result = rewrite_with_gemini(
        item["title"],
        item["description"],
        item["link"]
    )

    if not result:
        result = fallback_post(item)

    write_post(result)


if __name__ == "__main__":
    main()