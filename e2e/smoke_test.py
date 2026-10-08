import json, os, sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE=os.getenv('RETAILPULSE_API','http://127.0.0.1:8000/api/v1')
EMAIL=os.getenv('RETAILPULSE_EMAIL','owner@retailpulse.ai')
PASSWORD=os.getenv('RETAILPULSE_PASSWORD','owner123')

def call(path, method='GET', body=None, token=None):
    data=None
    headers={'Content-Type':'application/json'}
    if body is not None:data=json.dumps(body).encode()
    if token:headers['Authorization']='Bearer '+token
    req=Request(BASE+path,data=data,headers=headers,method=method)
    try:
        with urlopen(req,timeout=30) as r:return r.status,json.loads(r.read().decode())
    except HTTPError as e:
        print(f'FAIL {method} {path}: HTTP {e.code} {e.read().decode()}')
        raise

def main():
    s,h=call('/health')
    assert s==200 and h['status']=='healthy'
    s,x=call('/auth/login','POST',{'email':EMAIL,'password':PASSWORD})
    assert s==200 and x.get('access_token')
    token=x['access_token']
    for path in ['/auth/me','dashboard','products','alerts','reports/summary?days=30','restock/center']:
        s,_=call('/'+path,token=token)
        assert s==200,(path,s)
    products=call('/products',token=token)[1]
    assert products, 'No demo products found'
    pid=products[0]['id']
    for path in [f'/seasonality?product_id={pid}',f'/anomalies?product_id={pid}',f'/inventory/advisor?product_id={pid}',f'/scenarios/compare?product_id={pid}&horizon=30']:
        s,_=call(path,token=token);assert s==200,(path,s)
    print('E2E smoke test: PASS')

if __name__=='__main__':main()
