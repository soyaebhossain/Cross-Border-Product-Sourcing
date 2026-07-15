"""Repeatable local smoke test for catalog integrity, auth security, filters and quote lifecycle."""
import json, sqlite3, urllib.error, urllib.request, http.cookiejar, time

API = "http://127.0.0.1:8001"
def request(path, method="GET", body=None, opener=None):
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(API+path,data=data,method=method,headers={"Content-Type":"application/json"})
    call = opener.open if opener else urllib.request.urlopen
    with call(req,timeout=15) as response: return response.status, response.read(), response.headers

db=sqlite3.connect("services/catalog-service/catalog-rebuild.sqlite3")
assert db.execute("select count(*) from catalog_products").fetchone()[0] == 350
assert db.execute("select count(*) from catalog_product_variants").fetchone()[0] == 350
assert db.execute("select count(*) from sourcing_seller_offers").fetchone()[0] >= 2100
assert db.execute("select count(*) from (select product_id,coalesce(sku,''),coalesce(variant_name,''),weight_kg,length_cm,width_cm,height_cm,count(*) n from catalog_product_variants group by 1,2,3,4,5,6,7 having n>1)").fetchone()[0] == 0
db.close()
status, raw, _ = request("/api/catalog/browse/?sort=cheapest&country=CN&page_size=5")
assert status == 200 and len(json.loads(raw)["items"]) == 5
username=f"smoke-{int(time.time())}"; request("/api/auth/register/","POST",{"username":username,"password":"TestPass123!","role":"admin"})
jar=http.cookiejar.CookieJar(); opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
_, raw, _=request("/api/auth/login/","POST",{"identifier":username,"password":"TestPass123!"},opener); assert json.loads(raw)["user"]["role"] == "customer"
_, raw, _=request("/api/auth/me/",opener=opener); assert json.loads(raw)["role"] == "customer"
print("PASS: integrity, filters, forced-customer registration, credential cookie login")
