#!/usr/bin/env python3
"""
Vinted Notifier: controlla una o più ricerche Vinted e invia una notifica
Telegram per ogni nuovo articolo pubblicato.

Uso:
    python vinted_notifier.py            # gira in continuo
    python vinted_notifier.py --once     # un solo controllo (per cron / Task Scheduler)
    python vinted_notifier.py --test     # invia un messaggio di prova su Telegram
"""
import argparse
import html
import json
import os
import re
import random
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlencode

import requests

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
SEEN_FILE = BASE_DIR / "seen_items.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)

def log(msg):
    print(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg, flush=True)


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_json(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def normalize_search_url(search_url):
    """Controlla l'URL della ricerca e forza l'ordinamento per data (più recenti prima)."""
    u = urlparse(search_url.strip())
    if not u.netloc or "vinted" not in u.netloc:
        raise ValueError(f"Non sembra un URL di Vinted: {search_url}")
    query = [(k, v) for k, v in parse_qsl(u.query) if k not in ("order", "page", "time", "search_id")]
    query.append(("order", "newest_first"))
    domain = f"{u.scheme or 'https'}://{u.netloc}"
    return domain, f"{domain}{u.path or '/catalog'}?{urlencode(query, safe='[]')}"


class VintedClient:
    """Legge la pagina dei risultati di ricerca del sito, come farebbe un browser.

    Da settembre 2026 le API di Vinted restituiscono gli articoli del mercato del
    paese da cui arriva la richiesta (per GitHub: Stati Uniti), mentre la pagina
    del sito rispetta dominio e filtri.
    """

    def __init__(self):
        self.sessions = {}

    def _session(self, domain, refresh=False):
        if refresh or domain not in self.sessions:
            s = requests.Session()
            s.headers.update({
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
            })
            s.get(domain + "/", timeout=20)
            self.sessions[domain] = s
        return self.sessions[domain]

    def search(self, search_url):
        domain, url = normalize_search_url(search_url)
        for attempt in range(2):
            r = self._session(domain, refresh=attempt > 0).get(url, timeout=30)
            if r.status_code in (401, 403) and attempt == 0:
                continue  # cookie scaduti: rinnova la sessione e riprova
            if r.status_code == 429:
                raise RuntimeError("Vinted sta limitando le richieste (429): aumenta l'intervallo")
            r.raise_for_status()
            items = parse_catalog_html(r.text, domain)
            if not items and "feed-grid" not in r.text:
                raise RuntimeError("Pagina di Vinted senza articoli leggibili: forse è cambiato il sito")
            return domain, items
        raise RuntimeError(f"Accesso negato da Vinted (HTTP {r.status_code})")


ITEM_LINK_RE = re.compile(
    r'<a href="(/items/(\d+)[^"?]*)[^"]*"[^>]*data-testid="product-item-id-\d+--overlay-link"[^>]*title="([^"]*)"')
ITEM_IMG_RE = re.compile(r'<img src="([^"]+)"[^>]*data-testid="product-item-id-(\d+)--image--img"')
PRICE_RE = re.compile(r"^\d[\d.,]*\s?€$")
FIELD_KEYS = ("Brand", "Marca", "Condizioni", "Taglia")


def parse_item_title(text):
    """'Titolo, Brand: X, Condizioni: Y, Taglia: L, 15.00 €, 16.45 €' -> campi."""
    parts = [p.strip() for p in html.unescape(text).split(", ")]
    prices = []
    while parts and PRICE_RE.match(parts[-1]):
        prices.insert(0, parts.pop())
    fields, title_parts = {}, []
    for p in parts:
        key, sep, value = p.partition(": ")
        if sep and key in FIELD_KEYS and value:
            fields[key] = value
        elif not fields:
            title_parts.append(p)
    return {
        "title": ", ".join(title_parts) or "(senza titolo)",
        "price": prices[0] if prices else "?",
        "total": prices[1] if len(prices) > 1 else None,
        "brand": fields.get("Brand") or fields.get("Marca") or "",
        "size": fields.get("Taglia", ""),
        "status": fields.get("Condizioni", ""),
    }


def parse_catalog_html(page, domain):
    photos = {item_id: html.unescape(src) for src, item_id in ITEM_IMG_RE.findall(page)}
    items, seen_ids = [], set()
    for href, item_id, title in ITEM_LINK_RE.findall(page):
        if item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        items.append({"id": item_id, "url": domain + html.unescape(href), "photo": photos.get(item_id),
                      **parse_item_title(title)})
    return items


def html_escape(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Telegram:
    def __init__(self, token, chat_id):
        self.api = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id

    def send_text(self, text):
        r = requests.post(self.api + "/sendMessage", timeout=20, data={
            "chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
            "disable_web_page_preview": "false",
        })
        r.raise_for_status()

    def send_item(self, search_name, f):
        lines = [f"🆕 <b>{html_escape(search_name)}</b>", f"<b>{html_escape(f['title'])}</b>"]
        price_line = f"💶 {html_escape(f['price'])}"
        if f["total"]:
            price_line += f" (con protezione: {html_escape(f['total'])})"
        lines.append(price_line)
        details = " · ".join(x for x in (f["brand"], f["size"], f["status"]) if x)
        if details:
            lines.append(html_escape(details))
        lines.append(f'<a href="{f["url"]}">Apri su Vinted</a>')
        caption = "\n".join(lines)
        if f["photo"]:
            try:
                r = requests.post(self.api + "/sendPhoto", timeout=20, data={
                    "chat_id": self.chat_id, "photo": f["photo"],
                    "caption": caption, "parse_mode": "HTML",
                })
                r.raise_for_status()
                return
            except requests.RequestException:
                pass  # se la foto non va, manda solo il testo
        self.send_text(caption)


def check_all(config, client, telegram, seen):
    errors = 0
    for search in config["searches"]:
        name = search.get("name") or search["url"]
        if search.get("paused"):
            continue
        try:
            domain, items = client.search(search["url"])
        except Exception as e:
            log(f"Errore su '{name}': {e}")
            errors += 1
            continue

        known = set(seen.get(search["url"], []))
        first_run = search["url"] not in seen
        new_items = [i for i in items if str(i["id"]) not in known]
        failed = set()

        if first_run:
            # Al primo giro registra gli articoli già presenti senza notificarli
            log(f"'{name}': primo controllo, {len(items)} articoli memorizzati (nessuna notifica)")
            try:
                telegram.send_text(f"✅ Ricerca <b>{html_escape(name)}</b> attiva: {len(items)} articoli "
                                   "già presenti. Da ora ti avviso solo dei nuovi.")
            except requests.RequestException as e:
                log(f"Errore Telegram: {e}")
        else:
            # Dal più vecchio al più recente, così su Telegram restano in ordine
            for item in reversed(new_items):
                f = item
                try:
                    telegram.send_item(name, f)
                    log(f"'{name}': notificato {f['title']} ({f['price']})")
                except requests.RequestException as e:
                    log(f"Errore Telegram: {e}")
                    failed.add(f["id"])  # riprova al prossimo giro
                    continue
                time.sleep(1)
            if not new_items:
                log(f"'{name}': nessun articolo nuovo")

        known.update(str(i["id"]) for i in items if str(i["id"]) not in failed)
        # Tiene solo gli ultimi 1000 id per ricerca
        seen[search["url"]] = list(known)[-1000:]
        save_json(SEEN_FILE, seen)
        time.sleep(random.uniform(2, 5))
    return errors


def main():
    parser = argparse.ArgumentParser(description="Notifiche Telegram per i nuovi articoli su Vinted")
    parser.add_argument("--once", action="store_true", help="esegue un solo controllo ed esce")
    parser.add_argument("--test", action="store_true", help="invia un messaggio di prova su Telegram")
    args = parser.parse_args()

    if not CONFIG_FILE.exists():
        sys.exit(f"Manca {CONFIG_FILE.name}: copia config.example.json in config.json e compilalo.")
    config = load_json(CONFIG_FILE, {})
    tg = dict(config.get("telegram", {}))
    # Su GitHub Actions token e chat id arrivano dai Secrets
    tg["bot_token"] = os.environ.get("TELEGRAM_BOT_TOKEN") or tg.get("bot_token", "")
    tg["chat_id"] = os.environ.get("TELEGRAM_CHAT_ID") or tg.get("chat_id", "")
    if not tg["bot_token"] or "INSERISCI" in tg["bot_token"] or not tg["chat_id"]:
        sys.exit("Inserisci bot_token e chat_id di Telegram in config.json.")
    telegram = Telegram(tg["bot_token"], tg["chat_id"])

    if args.test:
        telegram.send_text("✅ Vinted Notifier collegato correttamente.")
        log("Messaggio di prova inviato.")
        return

    if not any(not x.get("paused") for x in config.get("searches", [])):
        log("Nessuna ricerca in config.json: niente da controllare.")
        return

    client = VintedClient()
    seen = load_json(SEEN_FILE, {})
    interval = max(30, int(config.get("interval_seconds", 60)))

    while True:
        errors = check_all(config, client, telegram, seen)
        if args.once:
            # Se nessuna ricerca è andata a buon fine, esce con errore (GitHub ti avvisa)
            active = [x for x in config["searches"] if not x.get("paused")]
            if active and errors == len(active):
                sys.exit(1)
            break
        time.sleep(interval + random.uniform(0, 10))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Interrotto.")
