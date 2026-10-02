"""Run in the gateway image with network disabled; dummy credentials only."""
import json
from pathlib import Path
from types import SimpleNamespace
from mitmproxy import http
import gateway

g=gateway.addons[0]
g.token='test-only-dummy-secret'
url='https://ecds.ecmwf.int/api/retrieve/v1/processes/s2s-forecasts/execution'
inputs={'year':['2023'],'variable':'sea_surface_temperature'}
g.policy={'mode':'controlled','urls':[],'prefixes':[], 'retrievals':[{'url':url,'inputs':inputs}]}

def flow(method,url,body=None,headers=None):
    return SimpleNamespace(request=http.Request.make(method,url,json.dumps(body).encode() if body else b'',headers or {}),response=None,metadata={})

approved=flow('POST',url,{'inputs':inputs},{'PRIVATE-TOKEN':'agent-provided-not-trusted'})
g.request(approved)
assert approved.response is None
assert approved.request.headers['PRIVATE-TOKEN']=='test-only-dummy-secret'
for body in [{'inputs':{**inputs,'year':['2024']}},{'inputs':inputs,'subscriber':'https://example.com/write'}]:
    rejected=flow('POST',url,body);g.request(rejected);assert rejected.response.status_code==403
rejected=flow('POST','https://example.com/execution',{'inputs':inputs});g.request(rejected)
assert rejected.response.status_code==403
approved.response=http.Response.make(200,json.dumps({'jobID':'approved-job'}).encode())
g.response(approved)
job='https://ecds.ecmwf.int/api/retrieve/v1/jobs/approved-job/results'
own=flow('GET',job);g.request(own);assert own.response is None
other=flow('GET',job.replace('approved-job','other-job'));g.request(other)
assert other.response.status_code==403
download='https://example.com/approved-result?signature=private-query'
own.response=http.Response.make(200,json.dumps({'asset':{'href':download}}).encode());g.response(own)
result=flow('GET',download);g.request(result);assert result.response is None
assert 'PRIVATE-TOKEN' not in result.request.headers
log=Path('/state/network.jsonl').read_text()
assert 'test-only-dummy-secret' not in log and 'private-query' not in log
print(json.dumps({'passed':True,'exact_request_enforced':True,'only_own_jobs':True,
                  'credential_forwarding':'dummy_verified_no_live_request','audit_redacts_secrets':True}))
