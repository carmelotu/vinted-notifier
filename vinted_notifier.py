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
import json
import os
import random
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qsl

import requests

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
SEEN_FILE = BASE_DIR / "seen_items.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)

# Nomi dei parametri nell'URL del sito -> nomi usati dalle API di Vinted
PARAM_RENAME = {
    "catalog": "catalog_ids",
    "catalog_ids": "catalog_ids",
    "brand_ids": "brand_ids",
    "size_ids": "size_ids",
    "status_ids": "status_ids",
    "color_ids": "color_ids",
    "material_ids": "material_ids",
    "video_game_platform_ids": "video_game_platform_ids",
    "patterns_ids": "patterns_ids",
}
# Parametri dell'URL del sito che non servono alle API
PARAM_SKIP = {"time", "search_id", "page", "per_page", "order", "disabled_personalization"}


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


def search_url_to_api(search_url, per_page=40):
    """Trasforma l'URL di una ricerca Vinted (copiato dal browser) nella chiamata API."""
    u = urlparse(search_url.strip())
    if not u.netloc or "vinted" not in u.netloc:
        raise ValueError(f"Non sembra un URL di Vinted: {search_url}")
    domain = f"{u.scheme or 'https'}://{u.netloc}"

    grouped = {}
    for key, value in parse_qsl(u.query, keep_blank_values=False):
        key = key.replace("[]", "")
        if key in PARAM_SKIP:
            continue
        key = PARAM_RENAME.get(key, key)
        grouped.setdefault(key, []).append(value)

    params = {k: ",".join(v) for k, v in grouped.items()}
    params["order"] = "newest_first"
    params["per_page"] = str(per_page)
    params["page"] = "1"
    return domain, params


class VintedClient:
    def __init__(self):
        self.sessions = {}

    def _session(self, domain, refresh=False):
        if refresh or domain not in self.sessions:
            s = requests.Session()
            s.headers.update({
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
            })
            # La homepage imposta i cookie di sessione necessari alle API
            s.get(domain + "/", timeout=20)
            self.sessions[domain] = s
        return self.sessions[domain]

    def search(self, search_url):
        domain, params = search_url_to_api(search_url)
        for attempt in range(2):
            s = self._session(domain, refresh=attempt > 0)
            r = s.get(domain + "/api/v2/catalog/items", params=params, timeout=20,
                      headers={"Referer": search_url})
            if r.status_code in (401, 403) and attempt == 0:
                continue  # cookie scaduti: rinnova la sessione e riprova
            if r.status_code == 429:
                raise RuntimeError("Vinted sta limitando le richieste (429): aumenta l'intervallo")
            r.raise_for_status()
            return domain, r.json().get("items", [])
        raise RuntimeError(f"Accesso negato dalle API di Vinted (HTTP {r.status_code})")


def item_fields(item, domain):
    price = item.get("price")
    if isinstance(price, dict):
        price = f"{price.get('amount')} {price.get('currency_code', '')}".strip()
    total = item.get("total_item_price")
    if isinstance(total, dict):
        total = f"{total.get('amount')} {total.get('currency_code', '')}".strip()
    photo = item.get("photo") or {}
    url = item.get("url") or f"{domain}/items/{item.get('id')}"
    return {
        "id": str(item.get("id")),
        "title": item.get("title", "(senza titolo)"),
        "price": price or "?",
        "total": total,
        "brand": item.get("brand_title") or "",
        "size": item.get("size_title") or "",
        "status": item.get("status") or "",
        "photo": photo.get("url") or photo.get("full_size_url"),
        "url": url,
    }


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
        try:
            domain, items = client.search(search["url"])
        except Exception as e:
            log(f"Errore su '{name}': {e}")
            errors += 1
            continue

        known = set(seen.get(search["url"], []))
        first_run = search["url"] not in seen
        new_items = [i for i in items if str(i.get("id")) not in known]
        failed = set()

        if first_run:
            # Al primo giro registra gli articoli già presenti senza notificarli
            log(f"'{name}': primo controllo, {len(items)} articoli memorizzati (nessuna notifica)")
        else:
            # Dal più vecchio al più recente, così su Telegram restano in ordine
            for item in reversed(new_items):
                f = item_fields(item, domain)
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

        known.update(str(i.get("id")) for i in items if str(i.get("id")) not in failed)
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

    if not config.get("searches"):
        sys.exit("Aggiungi almeno una ricerca in 'searches' dentro config.json.")

    client = VintedClient()
    seen = load_json(SEEN_FILE, {})
    interval = max(30, int(config.get("interval_seconds", 60)))

    while True:
        errors = check_all(config, client, telegram, seen)
        if args.once:
            # Se nessuna ricerca è andata a buon fine, esce con errore (GitHub ti avvisa)
            if errors == len(config["searches"]):
                sys.exit(1)
            break
        time.sleep(interval + random.uniform(0, 10))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Interrotto.")
