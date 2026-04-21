import os
import re
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# ── Configurações ──────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
OUTPUT_DIR = "src/content/post"

# Feeds RSS de tecnologia (todos gratuitos, sem autenticação)
RSS_FEEDS = [
    "https://feeds.feedburner.com/TechCrunch",
    "https://hnrss.org/frontpage",          # Hacker News
    "https://www.theverge.com/rss/index.xml",
]

MAX_POSTS = 4  # quantas notícias buscar por execução


# ── Helpers ────────────────────────────────────────────────────────────────────
def fetch_url(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_rss_items(feed_url: str, limit: int = 5) -> list[dict]:
    """Retorna os N itens mais recentes de um feed RSS."""
    try:
        raw = fetch_url(feed_url)
        root = ET.fromstring(raw)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = []

        # Suporte a RSS 2.0 e Atom
        for item in root.iter("item"):
            title = item.findtext("title", "").strip()
            desc  = item.findtext("description", "").strip()
            link  = item.findtext("link", "").strip()
            if title and link:
                items.append({"title": title, "description": desc[:500], "link": link})
            if len(items) >= limit:
                break

        if not items:
            for entry in root.findall(".//atom:entry", ns):
                title = entry.findtext("atom:title", "", ns).strip()
                link_el = entry.find("atom:link", ns)
                link  = (link_el.get("href", "") if link_el is not None else "").strip()
                desc  = entry.findtext("atom:summary", "", ns).strip()
                if title and link:
                    items.append({"title": title, "description": desc[:500], "link": link})
                if len(items) >= limit:
                    break

        return items
    except Exception as e:
        print(f"  [aviso] Falha ao ler {feed_url}: {e}")
        return []


def rewrite_with_gemini(title: str, description: str, source_link: str) -> dict | None:
    """
    Chama a API do Gemini (gemini-2.0-flash — gratuito) para reescrever a notícia.
    Retorna dict com title, description, tags, body ou None em caso de erro.
    """
    prompt = f"""Você é um redator de blog de tecnologia em português brasileiro.
Reescreva a notícia abaixo como um post de blog original, informativo e envolvente.

Notícia original:
Título: {title}
Resumo: {description}
Link fonte: {source_link}

Responda APENAS com JSON válido no seguinte formato (sem markdown, sem texto fora do JSON):
{{
  "title": "Título em português, criativo e direto",
  "description": "Resumo de 1 frase em português (máx 160 caracteres)",
  "tags": ["tag1", "tag2", "tag3"],
  "body": "Corpo do post em Markdown, entre 300 e 500 palavras, em português brasileiro. Cite a fonte original ao final com um link."
}}"""

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}
    }).encode("utf-8")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

        # Remove possíveis blocos de código ```json ... ```
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

        return json.loads(text)
    except Exception as e:
        print(f"  [erro] Gemini falhou: {e}")
        return None


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[áàãâä]", "a", text)
    text = re.sub(r"[éèêë]", "e", text)
    text = re.sub(r"[íìîï]", "i", text)
    text = re.sub(r"[óòõôö]", "o", text)
    text = re.sub(r"[úùûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:60]


def write_post(post_data: dict) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug  = slugify(post_data["title"])
    tags  = "\n".join(f"  - {t}" for t in post_data.get("tags", ["tecnologia"]))

    frontmatter = f"""---
title: {post_data['title']}
description: {post_data['description']}
tags:
{tags}
pubDate: {today}
---

"""
    content = frontmatter + post_data["body"]
    filename = f"{today}-{slug}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print("🔍 Buscando notícias nos feeds RSS...")
    all_items: list[dict] = []
    for feed in RSS_FEEDS:
        print(f"  → {feed}")
        all_items.extend(fetch_rss_items(feed, limit=3))

    # Deduplica por título e limita
    seen: set[str] = set()
    unique_items: list[dict] = []
    for item in all_items:
        key = item["title"].lower()[:80]
        if key not in seen:
            seen.add(key)
            unique_items.append(item)
        if len(unique_items) >= MAX_POSTS:
            break

    print(f"\n✨ {len(unique_items)} notícias selecionadas. Reescrevendo com Gemini...\n")
    generated = 0
    for item in unique_items:
        print(f"  Processando: {item['title'][:70]}...")
        result = rewrite_with_gemini(item["title"], item["description"], item["link"])
        if result:
            path = write_post(result)
            print(f"  ✅ Gerado: {path}")
            generated += 1
        else:
            print(f"  ⚠️  Pulado (erro na IA)")

    print(f"\n🎉 {generated} post(s) criado(s) em '{OUTPUT_DIR}/'")


if __name__ == "__main__":
    main()