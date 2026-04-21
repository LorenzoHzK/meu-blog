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


# ── Gemini ────────────────────────────────────────────
def rewrite_with_gemini(title, description, link):
    if not GEMINI_API_KEY:
        print("[erro] sem API KEY")
        return None

    prompt = f"""
Escreva um artigo de blog em português brasileiro.

REGRAS:
- primeira pessoa
- estilo pessoal
- markdown (##)
- mínimo 800 palavras
- sem inglês

Tema:
{title}

Resumo:
{description}

Fonte:
{link}

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
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        text = re.sub(r"```json|```", "", text).strip()

        result = json.loads(text)

        if len(result["body"].split()) < 400:
            print("[gemini] texto muito curto")
            return None

        print("[gemini] sucesso")
        return result

    except Exception as e:
        print(f"[erro Gemini] {e}")
        return None


# ── Fallback ──────────────────────────────────────────
def fallback_post(item):
    print("[fallback] ativado")

    body = f"""
## Minha visão sobre isso

Recentemente vi algo interessante:

**{item['title']}**

Mesmo sendo um conteúdo originalmente em inglês, o ponto principal é bem claro.

## O que isso significa

Esse tipo de conteúdo mostra como o mercado de tecnologia está mudando rápido.

Hoje, ferramentas de inteligência artificial estão influenciando diretamente como as pessoas encontram conteúdo.

## Minha opinião

Eu acho isso interessante porque muda completamente o jogo.

Antes tudo dependia de SEO, agora estamos entrando em um cenário onde a IA começa a intermediar tudo.

## Pontos positivos

- Novas oportunidades
- Crescimento da IA
- Mudança no comportamento digital

## Pontos negativos

- Dependência de plataformas
- Menos controle sobre tráfego

## Conclusão

No geral, achei interessante acompanhar esse tipo de evolução.

Ainda não uso isso diretamente, mas é algo que com certeza pode impactar projetos no futuro.

Fonte: {item['link']}
"""

    return {
        "title": "Como a IA está mudando o tráfego na internet",
        "description": "Reflexão sobre o impacto da IA no SEO e no tráfego digital.",
        "tags": ["ia", "tecnologia"],
        "body": body
    }


# ── Writer ────────────────────────────────────────────
def write_post(post):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    slug = re.sub(r"[^a-z0-9]+", "-", post["title"].lower())[:60]

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

    items = []

    for feed in RSS_FEEDS:
        items.extend(fetch_rss_items(feed))

    if not items:
        print("[erro] sem notícias — criando post genérico")
        post = fallback_post({
            "title": "Tecnologia e IA em crescimento",
            "description": "O mercado de tecnologia continua evoluindo rapidamente.",
            "link": "#"
        })
        write_post(post)
        return

    item = items[0]
    print(f"[usando] {item['title']}")

    post = rewrite_with_gemini(
        item["title"],
        item["description"],
        item["link"]
    )

    if not post:
        post = fallback_post(item)

    write_post(post)

    print("✅ FINALIZADO COM SUCESSO")


if __name__ == "__main__":
    main()