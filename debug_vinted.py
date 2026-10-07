import requests, re
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
s=requests.Session(); s.headers.update({"User-Agent":UA,"Accept-Language":"it-IT,it;q=0.9"})
s.get("https://www.vinted.it/",timeout=20)
tok=s.cookies.get("access_token_web"); H={"Authorization":f"Bearer {tok}","Accept":"application/json"}
for u in ["https://api.vinted.it/svc-catalogue/brands?keyword=barbour","https://api.vinted.it/svc-catalogue/filters/brands?keyword=barbour","https://www.vinted.it/api/v2/brands?keyword=barbour","https://api.vinted.it/svc-catalogue/brands/search?keyword=barbour","https://www.vinted.it/api/v2/catalog/filters/search?filter_code=brand&filter_search_text=barbour","https://api.vinted.it/svc-catalogue/filters/search?filter_code=brand&filter_search_text=barbour"]:
    try:
        r=s.get(u,headers=H,timeout=20); print("API",r.status_code,u,r.text[:300].replace("\n"," "))
    except Exception as e: print("API ERR",u,e)
for u in ["https://www.vinted.it/brand/barbour","https://www.vinted.it/catalog?search_text=barbour"]:
    t=s.get(u,timeout=20).text; n=0
    for m in re.finditer(r'[Bb]arbour',t):
        ctx=t[max(0,m.start()-120):m.end()+80]
        if re.search(r'(brand|Brand|slug|\\"id\\")',ctx):
            print("CTX",u[-20:],ctx.replace("\n"," ")); n+=1
            if n>=8: break
