import requests, json
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
s=requests.Session(); s.headers.update({"User-Agent":UA,"Accept":"application/json, text/plain, */*","Accept-Language":"it-IT,it;q=0.9"})
r=s.get("https://www.vinted.it/",timeout=20); print("home",r.status_code)
print("cookies",{c.name:(c.domain,len(c.value)) for c in s.cookies})
tok=s.cookies.get("access_token_web"); anon=s.cookies.get("anon_id")
h={"Authorization":f"Bearer {tok}","Origin":"https://www.vinted.it","Referer":"https://www.vinted.it/"}
if anon: h["x-anon-id"]=anon
base={"search_text":"cargo uomo","order":"newest_first","per_page":"5","page":"1","price_from":"0","price_to":"15"}
variants={
 "plain":{},
 "comma":{"attribute_ids[catalog]":"34","attribute_ids[size]":"209,210","attribute_ids[brand]":"1153,259,362,872289,65","attribute_ids[status]":"2,6,1,3"},
 "repeat":[("attribute_ids[catalog][]","34"),("attribute_ids[size][]","209"),("attribute_ids[size][]","210"),("attribute_ids[brand][]","1153"),("attribute_ids[brand][]","65"),("attribute_ids[status][]","2"),("attribute_ids[status][]","6")],
 "repeat_nobr":[("attribute_ids[catalog]","34"),("attribute_ids[size]","209"),("attribute_ids[size]","210"),("attribute_ids[brand]","1153"),("attribute_ids[brand]","65"),("attribute_ids[status]","2"),("attribute_ids[status]","6")],
 "old_names":{"catalog_ids":"34","size_ids":"209,210","brand_ids":"1153,65","status_ids":"2,6"},
}
for name,extra in variants.items():
    p=list(base.items())+(list(extra.items()) if isinstance(extra,dict) else extra)
    r=s.get("https://api.vinted.it/svc-catalogue/items",params=p,headers=h,timeout=20)
    print("\n==",name,r.status_code,r.url[:300])
    try:
        j=r.json(); print("keys",list(j.keys()))
        it=j.get("items") or []
        print("n",len(it))
        for x in it[:3]: print(json.dumps({k:x.get(k) for k in ("id","title","price","total_item_price","brand_title","size_title","status","url")},ensure_ascii=False)[:400]); 
        if it: print("item keys",list(it[0].keys())); print("photo",json.dumps(it[0].get("photo"))[:300])
    except Exception as e: print("body",r.text[:300])
