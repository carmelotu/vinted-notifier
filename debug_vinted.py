import requests, json, base64, re
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
def sess():
    s=requests.Session(); s.headers.update({"User-Agent":UA,"Accept":"application/json, text/plain, */*","Accept-Language":"it-IT,it;q=0.9"})
    s.get("https://www.vinted.it/",timeout=20); return s
s=sess()
tok=s.cookies.get("access_token_web"); anon=s.cookies.get("anon_id")
pl=tok.split(".")[1]; pl+="="*(-len(pl)%4)
claims=json.loads(base64.urlsafe_b64decode(pl)); print("claims keys",{k:v for k,v in claims.items() if k not in("sub","jti","sid")})
print("locale cookie", s.cookies.get("anonymous-iso-locale"))
H={"Authorization":f"Bearer {tok}","x-anon-id":anon,"Origin":"https://www.vinted.it","Referer":"https://www.vinted.it/"}
base={"search_text":"cargo uomo","order":"newest_first","per_page":"3","page":"1","price_to":"15","attribute_ids[catalog]":"34","attribute_ids[size]":"209,210","attribute_ids[brand]":"1153,259,362,872289,65","attribute_ids[status]":"2,6,1,3"}
def show(name,r):
    try:
        it=r.json().get("items",[]); print("==",name,r.status_code,[(x["title"][:30],x["price"]["currency_code"]) for x in it])
    except Exception: print("==",name,r.status_code,r.text[:200])
show("base",s.get("https://api.vinted.it/svc-catalogue/items",params=base,headers=H,timeout=20))
show("currency",s.get("https://api.vinted.it/svc-catalogue/items",params={**base,"currency":"EUR"},headers=H,timeout=20))
for hk,hv in [("X-Vinted-Country","IT"),("x-country-code","IT"),("Accept-Language","it-IT"),("x-locale","it-IT"),("X-Money-Object","true")]:
    show("hdr "+hk,s.get("https://api.vinted.it/svc-catalogue/items",params=base,headers={**H,hk:hv},timeout=20))
show("www host",s.get("https://www.vinted.it/svc-catalogue/items",params=base,headers=H,timeout=20))
show("www api/v2/catalog",s.get("https://www.vinted.it/api/v2/catalog/items",params={"search_text":"cargo uomo","per_page":"3"},timeout=20))
r=s.get("https://www.vinted.it/catalog?search_text=cargo%20uomo&catalog[]=34&price_to=15",headers={"Accept":"text/html"},timeout=20)
print("html",r.status_code,len(r.text),"items found",len(set(re.findall(r'/items/(\d+)',r.text))),"EUR" in r.text,"USD" in r.text, "$" in r.text)
print(r.text[:300].replace("\n"," "))
for m in re.findall(r'(svc-[a-z-]+/[a-z/_-]+|/api/v2/[a-z/_-]+)',r.text)[:30]: print("ref",m)
