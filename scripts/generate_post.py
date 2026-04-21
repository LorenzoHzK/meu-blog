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

MAX_POSTS = 1  # 🔥 AGORA APENAS 1 POST


def fetch_url(url):
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

        return items
    except:
        return []


def rewrite_with_gemini(title, description, link):
    prompt = f"""
Você é um desenvolvedor brasileiro escrevendo um blog pessoal de tecnologia.

Escreva um post no estilo:
- primeira pessoa
- opinativo
- natural (como alguém explicando experiência própria)
- com títulos e subtítulos em markdown (##)

ESTILO:
- parecido com um relato pessoal
- simples de ler
- organizado
- com opinião sincera
- nada robótico

ESTRUTURA:
- introdução pessoal
- explicação do tema
- comparação ou análise
- conclusão com opinião

REGRAS:
- português brasileiro
- NÃO usar HTML
- usar markdown
- entre 400 e 800 palavras

DADOS:
Título: {title}
Resumo: {description}
Link: {link}

Retorne JSON:

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
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        text = re.sub(r"```json|```", "", text).strip()

        return json.loads(text)

    except:
        return None


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

    print(f"[OK] {path}")


def main():
    items = []

    for feed in RSS_FEEDS:
        items.extend(fetch_rss_items(feed))

    if not items:
        print("Nenhuma notícia encontrada")
        return

    item = items[0]  # 🔥 pega só UMA notícia

    print(f"Gerando post para: {item['title']}")

    result = rewrite_with_gemini(
        item["title"],
        item["description"],
        item["link"]
    )

    if not result:
        print("Erro na IA")
        return

    write_post(result)


if __name__ == "__main__":
    main()