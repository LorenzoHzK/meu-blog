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
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
]

MAX_POSTS = 4


# ── Helpers ─────────────────────────────────────────────
def fetch_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;|&amp;|&lt;|&gt;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_rss_items(feed_url, limit=5):
    try:
        raw = fetch_url(feed_url)
        root = ET.fromstring(raw)
        items = []

        for item in root.iter("item"):
            title = clean_html(item.findtext("title", "").strip())
            desc = clean_html(item.findtext("description", "").strip())
            link = item.findtext("link", "").strip()

            if title and link:
                items.append({
                    "title": title,
                    "description": desc[:500],
                    "link": link
                })

            if len(items) >= limit:
                break

        return items

    except Exception as e:
        print(f"[erro RSS] {e}")
        return []


def rewrite_with_gemini(title, description, link):
    if not GEMINI_API_KEY:
        return None

    prompt = f"""
Você é um redator profissional de tecnologia no Brasil.

Transforme a notícia abaixo em um artigo ORIGINAL, claro e interessante.

REGRAS:
- Escreva 100% em português brasileiro
- NÃO use HTML
- NÃO copie o texto original
- Explique de forma simples
- 300 a 500 palavras
- Gere título chamativo
- Gere descrição curta (até 160 caracteres)
- Gere 3 a 5 tags

DADOS:
Título: {title}
Resumo: {description}
Link: {link}

Responda apenas JSON válido:

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
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        text = re.sub(r"```json|```", "", text).strip()

        return json.loads(text)

    except Exception as e:
        print(f"[erro Gemini] {e}")
        return None


def slugify(text):
    text = text.lower()
    text = re.sub(r"[áàãâä]", "a", text)
    text = re.sub(r"[éèêë]", "e", text)
    text = re.sub(r"[íìîï]", "i", text)
    text = re.sub(r"[óòõôö]", "o", text)
    text = re.sub(r"[úùûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:60]


def safe_yaml(text: str) -> str:
    if not text:
        return ""
    text = str(text)
    text = text.replace('"', '\\"')
    text = text.replace("\n", " ")
    text = text.replace(":", " -")
    return text.strip()


def write_post(post):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    title = safe_yaml(post["title"])
    description = safe_yaml(post["description"])
    slug = slugify(title)

    tags_list = post.get("tags", ["tecnologia"])
    tags = "\n".join(f'  - "{safe_yaml(t)}"' for t in tags_list)

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

    print(f"[OK] {path}")


def fallback_post(item):
    return {
        "title": item["title"],
        "description": item["description"][:120],
        "tags": ["tecnologia"],
        "body": f"{item['description']}\n\nFonte: {item['link']}"
    }


def main():
    all_items = []

    for feed in RSS_FEEDS:
        all_items.extend(fetch_rss_items(feed, 3))

    seen = set()
    selected = []

    for item in all_items:
        key = item["title"][:80]
        if key not in seen:
            seen.add(key)
            selected.append(item)

        if len(selected) >= MAX_POSTS:
            break

    print(f"{len(selected)} notícias encontradas")

    count = 0

    for item in selected:
        print(f"Processando: {item['title'][:60]}...")

        result = rewrite_with_gemini(
            item["title"],
            item["description"],
            item["link"]
        )

        if not result:
            print("[fallback usado]")
            result = fallback_post(item)

        write_post(result)
        count += 1

    print(f"{count} posts gerados com sucesso")


if __name__ == "__main__":
    main()