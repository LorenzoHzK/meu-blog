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

MAX_ITEMS = 4


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


# ── Gemini (ULTRA DENSO) ─────────────────────────────
def rewrite_with_gemini(items):
    if not GEMINI_API_KEY:
        print("[erro] sem API KEY")
        return None

    noticias = "\n\n".join([
        f"Título: {i['title']}\nResumo: {i['description']}\nLink: {i['link']}"
        for i in items
    ])

    prompt = f"""
Você é um desenvolvedor brasileiro escrevendo um blog pessoal.

Seu objetivo NÃO é resumir notícias.
Seu objetivo é ESCREVER UM ARTIGO PROFUNDO, detalhado e opinativo.

━━━━━━━━━━━━━━━━━━━
⚠️ REGRAS ABSOLUTAS
━━━━━━━━━━━━━━━━━━━

- Escreva 100% em português brasileiro
- Proibido usar inglês
- Proibido escrever pouco
- Proibido ser superficial
- Escreva como se fosse SUA opinião real

━━━━━━━━━━━━━━━━━━━
📏 TAMANHO
━━━━━━━━━━━━━━━━━━━

- MÍNIMO: 2000 palavras
- Conteúdo denso e explicativo

━━━━━━━━━━━━━━━━━━━
🧠 ESTRUTURA
━━━━━━━━━━━━━━━━━━━

## Introdução
- Contextualização real

## Para CADA notícia:

### O que aconteceu
### Como isso funciona
### Minha opinião
### Impacto real
### Exemplo prático

## Conclusão

━━━━━━━━━━━━━━━━━━━
📥 NOTÍCIAS
━━━━━━━━━━━━━━━━━━━

{noticias}

━━━━━━━━━━━━━━━━━━━
📤 FORMATO
━━━━━━━━━━━━━━━━━━━

Retorne JSON válido:

{{
  "title": "Resumo semanal de tecnologia",
  "description": "Resumo detalhado das principais notícias de tecnologia",
  "tags": ["tecnologia", "ia"],
  "body": "conteúdo completo em markdown"
}}
"""

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.85,
            "maxOutputTokens": 4096
        }
    }).encode("utf-8")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        text = re.sub(r"```json|```", "", text).strip()

        result = json.loads(text)

        if len(result["body"].split()) < 1200:
            print("[gemini] conteúdo fraco")
            return None

        print("[gemini] sucesso")
        return result

    except Exception as e:
        print(f"[erro Gemini] {e}")
        return None


# ── Fallback MULTI ─────────────────────────────────────
def fallback_post(items):
    print("[fallback] multi notícia")

    body = "## Resumo semanal de tecnologia\n\n"

    for item in items:
        body += f"""
---

## {item['title']}

### O que aconteceu

{item['description']}

### Minha visão

Essa notícia mostra como a tecnologia continua evoluindo rápido.

Mesmo sendo algo simples à primeira vista, isso pode ter impacto direto no mercado.

### Impacto

- Mudança no comportamento digital
- Crescimento da IA
- Novas oportunidades

Fonte: {item['link']}
"""

    return {
        "title": "Resumo semanal de tecnologia",
        "description": "Principais notícias da semana",
        "tags": ["tecnologia"],
        "body": body
    }


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
        print("[erro] sem notícias")
        post = fallback_post([{
            "title": "Tecnologia em evolução",
            "description": "Semana sem dados relevantes",
            "link": "#"
        }])
        write_post(post)
        return

    items = all_items[:MAX_ITEMS]

    print(f"[usando] {len(items)} notícias")

    post = rewrite_with_gemini(items)

    if not post:
        post = fallback_post(items)

    write_post(post)

    print("✅ FINALIZADO")


if __name__ == "__main__":
    main()