import requests, re
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
s=requests.Session(); s.headers.update({"User-Agent":UA,"Accept-Language":"it-IT,it;q=0.9"})
s.get("https://www.vinted.it/",timeout=20)
for u in ["https://www.vinted.it/brand/barbour","https://www.vinted.it/catalog?search_text=barbour"]:
    r=s.get(u,timeout=20); print("URL",u,"->",r.status_code,r.url)
    t=r.text
    for pat in [r'/brand/(\d+)-barbour', r'\\"id\\":(\d+),\\"title\\":\\"Barbour\\"', r'"id":(\d+),"title":"Barbour"', r'brand_ids?(?:%5B%5D|\[\])?=(\d+)[^"]{0,80}', r'(\d+)[^0-9]{1,40}Barbour']:
        m=re.findall(pat,t,re.I); print(" pat",pat[:40],sorted(set(m))[:15])
    for m in re.finditer(r'Barbour',t):
        ctx=t[max(0,m.start()-150):m.end()+60]
        if re.search(r'\d{2,}',ctx) and ('id' in ctx or 'brand' in ctx): print(" CTX",ctx.replace("\n"," ")); break
