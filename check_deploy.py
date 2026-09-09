import httpx
import time
import sys

SERVICE_ID = "srv-daa6eqajnfac73flvr70"
TOKEN = "rnd_XFXdigeT4JmIqIwtCcLZv2ruqIHe"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}

# 1. Eng so'nggi deployni aniqlaymiz
res = httpx.get(f"https://api.render.com/v1/services/{SERVICE_ID}/deploys", headers=HEADERS)
deploys = res.json()
if not deploys:
    print("Hech qanday deploy topilmadi.")
    sys.exit(1)

latest_deploy = deploys[0]['deploy']
deploy_id = latest_deploy['id']
print(f"Deploy ID: {deploy_id} boshlandi. Status: {latest_deploy['status']}")

# 2. Status 'live' bo'lguncha kutamiz
while True:
    res = httpx.get(f"https://api.render.com/v1/services/{SERVICE_ID}/deploys/{deploy_id}", headers=HEADERS)
    status = res.json()['status']
    print(f"Joriy status: {status}")
    if status in ['live', 'build_failed', 'update_failed', 'canceled']:
        print(f"Deploy yakunlandi: {status}")
        break
    time.sleep(10)
