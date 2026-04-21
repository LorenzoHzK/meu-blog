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
    "https://www.theverge.com/rss/full.xml",
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


# ── Gemini (OBRIGATÓRIO) ─────────────────────────────
def rewrite_with_gemini(items):
    if not GEMINI_API_KEY:
        raise Exception("❌ GEMINI_API_KEY não encontrada")

    print("[debug] API KEY OK")

    noticias = "\n\n".join([
        f"Título: {i['title']}\nResumo: {i['description']}\nLink: {i['link']}"
        for i in items
    ])

    prompt = f"""
Você é um desenvolvedor brasileiro escrevendo um blog pessoal.

REGRAS OBRIGATÓRIAS:
- Escreva 100% em português brasileiro
- NÃO USE INGLÊS EM NENHUM MOMENTO
- Conteúdo EXTREMAMENTE detalhado
- Mínimo de 1500 palavras
- Estilo humano, opinativo e técnico

ESTRUTURA:

## Introdução
Contextualize o cenário atual da tecnologia

## Para CADA notícia:

### O que aconteceu
Explique detalhadamente

### Como isso funciona
Explique tecnicamente

### Minha opinião
Opinião real, como dev

### Impacto real
Impacto no mercado e devs

### Exemplo prático
Dê exemplo real

## Conclusão
Resumo geral com visão de futuro

NOTÍCIAS:
{noticias}

Retorne SOMENTE JSON válido:

{{
  "title": "Resumo semanal de tecnologia",
  "description": "Resumo detalhado das principais notícias da semana",
  "tags": ["tecnologia", "ia", "programação"],
  "body": "conteúdo completo em markdown"
}}
"""

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": 4096
        }
    }).encode("utf-8")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())

        print("[debug] resposta recebida do Gemini")

        text = data["candidates"][0]["content"]["parts"][0]["text"]

        text = re.sub(r"```json|```", "", text).strip()

        match = re.search(r"\{.*\}", text, re.DOTALL)

        if not match:
            print(text)
            raise Exception("❌ Gemini não retornou JSON válido")

        result = json.loads(match.group(0))

        if len(result["body"].split()) < 800:
            raise Exception("❌ Conteúdo muito curto (IA falhou)")

        print("[gemini] sucesso total")
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