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
Você é um desenvolvedor brasileiro escrevendo um blog pessoal de tecnologia.

Seu objetivo é criar um post COMPLETO, detalhado e bem estruturado.

━━━━━━━━━━━━━━━━━━━
⚠️ REGRAS OBRIGATÓRIAS
━━━━━━━━━━━━━━━━━━━

- Escreva 100% em português brasileiro
- NÃO use inglês em nenhuma parte
- NÃO use HTML
- Use Markdown (## para títulos)
- Escreva em PRIMEIRA PESSOA
- Estilo natural, como experiência pessoal
- NÃO copie o texto original
- NÃO seja genérico

━━━━━━━━━━━━━━━━━━━
📏 TAMANHO
━━━━━━━━━━━━━━━━━━━

- MÍNIMO: 1200 palavras
- Texto longo e detalhado
- Explicações completas
- Nada de respostas curtas

━━━━━━━━━━━━━━━━━━━
🧠 ESTRUTURA OBRIGATÓRIA
━━━━━━━━━━━━━━━━━━━

1. Introdução pessoal
2. Explicação do tema
3. Análise/opinião
4. Pontos positivos
5. Pontos negativos
6. Comparações (se fizer sentido)
7. Conclusão pessoal

━━━━━━━━━━━━━━━━━━━
🎯 TOM
━━━━━━━━━━━━━━━━━━━

- Conversa natural
- Fluído
- Como um blog real (não IA)
- Pode usar exemplos pessoais
- Pode criticar

━━━━━━━━━━━━━━━━━━━
📥 DADOS
━━━━━━━━━━━━━━━━━━━

Título: {title}
Resumo: {description}
Link: {link}

━━━━━━━━━━━━━━━━━━━
📤 FORMATO DE RESPOSTA (OBRIGATÓRIO)
━━━━━━━━━━━━━━━━━━━

Retorne APENAS JSON válido:

{{
  "title": "Título em português chamativo",
  "description": "Resumo curto em português (máx 160 caracteres)",
  "tags": ["tecnologia", "ia", "software"],
  "body": "Conteúdo completo em markdown com mais de 1200 palavras"
}}
"""

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": 2048
        }
    }).encode("utf-8")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode())

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        text = re.sub(r"```json|```", "", text).strip()

        result = json.loads(text)

        # valida tamanho mínimo
        if len(result["body"].split()) < 800:
            print("[erro] texto muito curto")
            return None

        print("[gemini] sucesso (conteúdo longo)")
        return result

    except Exception as e:
        print(f"[erro Gemini] {e}")
        return None


def fallback_post(item):
    print("[fallback] gerando fallback melhorado")

    body = f"""
## O que eu achei sobre isso

Recentemente me deparei com uma notícia interessante:

**{item['title']}**

{item['description']}

Confesso que isso me chamou atenção, principalmente porque mostra como a tecnologia continua evoluindo de formas que a gente nem sempre espera.

## Minha visão

Mesmo sendo algo que ainda não faz parte direta do meu dia a dia, dá pra perceber que esse tipo de avanço pode impactar muita coisa no futuro.

A forma como essas soluções estão surgindo mostra que estamos caminhando para um cenário cada vez mais automatizado e inteligente.

## Pontos interessantes

- Crescimento da tecnologia
- Novas possibilidades
- Impacto no mercado

## Conclusão

No geral, achei interessante acompanhar esse tipo de evolução.  
Ainda quero testar mais coisas relacionadas a isso no futuro.

Fonte: {item['link']}
"""

    return {
        "title": item["title"],
        "description": item["description"][:120],
        "tags": ["tecnologia"],
        "body": body
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