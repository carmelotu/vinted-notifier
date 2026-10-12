import json, re, vinted_notifier as v
c = json.load(open("config.json"))
s = [x for x in c["searches"] if not x.get("paused")][0]
domain, url = v.normalize_search_url(s["url"])
cl = v.VintedClient()
sess = cl._session(domain)
page = sess.get(url, timeout=30).text
print("len", len(page))
print("items", len(v.parse_catalog_html(page, domain)), "with photo", sum(1 for i in v.parse_catalog_html(page, domain) if i["photo"]))
for m in list(re.finditer(r'<img[^>]*>', page))[:6]:
    print("IMG:", m.group(0)[:400])
i = page.find("--image--img")
print("CTX:", page[max(0, i-600):i+200])
