import json, os, requests, vinted_notifier as v
c = json.load(open("config.json"))
s = [x for x in c["searches"] if not x.get("paused")][0]
domain, items = v.VintedClient().search(s["url"])
it = items[0]
api = "https://api.telegram.org/bot" + os.environ["TELEGRAM_BOT_TOKEN"]
chat = os.environ["TELEGRAM_CHAT_ID"]
r = requests.post(api + "/sendPhoto", data={"chat_id": chat, "photo": it["photo"], "caption": "test link"})
print("VECCHIO METODO (link):", r.status_code, r.text[:200])
tg = v.Telegram(os.environ["TELEGRAM_BOT_TOKEN"], chat)
tg.send_photo(v.download_photo(it["photo"]), "🔧 Prova foto: ora le notifiche avranno l'immagine.")
print("NUOVO METODO: ok")
