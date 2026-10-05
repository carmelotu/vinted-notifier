import requests, re, json
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
s=requests.Session(); s.headers.update({"User-Agent":UA,"Accept-Language":"it-IT,it;q=0.9"})
s.get("https://www.vinted.it/",timeout=20)
url="https://www.vinted.it/catalog?search_text=cargo%20uomo&catalog[]=34&size_ids[]=209&size_ids[]=210&brand_ids[]=1153&brand_ids[]=259&brand_ids[]=362&brand_ids[]=872289&brand_ids[]=65&status_ids[]=2&status_ids[]=6&status_ids[]=1&status_ids[]=3&price_from=0&price_to=15&order=newest_first"
t=s.get(url,headers={"Accept":"text/html"},timeout=20).text
open("page.html","w").write(t)
lds=re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>',t,re.S)
print("LD count",len(lds))
for l in lds: print("LD",l[:1500])
ids=re.findall(r'/items/(\d+)',t); print("ids order",ids[:20])
i=t.find('/items/'); print("CTX1",t[i-1500:i+800])
for kw in ['"catalogItems"','"items":[','\\"items\\":[','"price":{"amount"','\\"price\\":{\\"amount\\"','__NEXT_DATA__']:
    j=t.find(kw); print("KW",kw,j, t[j:j+1200] if j>=0 else "")
