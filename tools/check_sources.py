"""Soru bankasındaki her sorunun kaynağını resmi dokümantasyonla karşılaştırır.

Her soruda:
  source_url : doğru cevabı destekleyen resmi Google Cloud dokümanı
  check      : o sayfada geçmesi gereken ifadeler (büyük/küçük harf duyarsız)

Kullanım (internet gerekir; uygulamanın kendisi çevrimdışı çalışır):
    python tools/check_sources.py                 # tüm sorular
    python tools/check_sources.py ace-012 ace-090 # belirli sorular

Google dokümanları değiştiğinde bu betik hangi soruların gözden geçirilmesi gerektiğini gösterir.
"""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = ("https://cloud.google.com/", "https://docs.cloud.google.com/")
MAX_PAGE_BYTES = 10 * 1024 * 1024


def is_allowed(url: str) -> bool:
    return isinstance(url, str) and url.startswith(ALLOWED)


class _AllowlistRedirects(urllib.request.HTTPRedirectHandler):
    """Yalnızca izin verilen resmi alan adlarına yönlendirmeleri takip eder."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_allowed(newurl):
            raise urllib.error.URLError(f"izin verilmeyen yönlendirme: {newurl[:200]}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_AllowlistRedirects)


def page_text(url: str, cache: dict) -> str:
    if url not in cache:
        if not is_allowed(url):
            raise ValueError("izin verilmeyen adres")
        req = urllib.request.Request(url, headers={"User-Agent": "gcp-ace-exam-trainer-source-check"})
        with _OPENER.open(req, timeout=40) as r:
            body = r.read(MAX_PAGE_BYTES + 1)
            if len(body) > MAX_PAGE_BYTES:
                raise ValueError("sayfa çok büyük")
            raw = body.decode("utf-8", "replace")
        raw = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", raw)
        txt = html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
        cache[url] = re.sub(r"\s+", " ", txt).lower()
    return cache[url]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'")).lower()


def main(argv: list[str]) -> int:
    qs = []
    for f in sorted((ROOT / "questions").glob("*.json")):
        qs += json.loads(f.read_text(encoding="utf-8"))
    if argv:
        qs = [q for q in qs if q["id"] in argv]
    cache: dict = {}
    urls = sorted({q["source_url"] for q in qs if is_allowed(q.get("source_url"))})

    def fetch(u):
        try:
            page_text(u, cache)
            return u, None
        except Exception as e:  # noqa: BLE001
            return u, str(e)

    with ThreadPoolExecutor(8) as ex:
        errors = dict(r for r in ex.map(fetch, urls) if r[1])

    bad = 0
    for q in qs:
        url, checks = q.get("source_url", ""), q.get("check", [])
        problems = []
        if not is_allowed(url):
            problems.append("resmi kaynak linki yok")
        elif url in errors:
            problems.append(f"sayfa açılamadı: {errors[url]}")
        elif not checks:
            problems.append("kontrol ifadesi yok")
        else:
            text = page_text(url, cache)
            problems += [f"sayfada yok: {c!r}" for c in checks if norm(c) not in text]
        if problems:
            bad += 1
            print(f"✗ {q['id']}  {url}\n    " + "\n    ".join(problems))
    print(f"\n{len(qs) - bad}/{len(qs)} soru kaynağıyla doğrulandı ({len(urls)} sayfa).")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
