"""Infrastructure probes only. No weather task, model call or forecast scoring."""
import json
import shlex
import tempfile
from pathlib import Path

from .common import ROOT, ARMS, read, write, inventory
from .runtime import Sandbox, carry_forward, docker, image_id


def python(box, source):
    result = box.execute('python -c '+shlex.quote(source), timeout=30)
    if result['exit_code']:
        raise RuntimeError(result['stderr'])
    return json.loads(result['stdout'])


def preflight():
    root = Path(tempfile.mkdtemp(prefix='sandbox-', dir=ROOT/'.preflight'))
    profiles = read(ROOT/'sandbox/profiles.yaml')['arms']
    results = dict(purpose='infrastructure_only_no_model_calls_no_benchmark_attempts', arms={}, passed=False,
                   gateway_image_id=image_id('accord-pilot-gateway:v1'))
    policy_state=root/'gateway-policy-test'
    policy_state.mkdir()
    write(policy_state/'policy.json',{'mode':'controlled','urls':[],'prefixes':[],'retrievals':[]})
    dry=docker('run','--rm','--network','none','--entrypoint','python',
               '--mount',f'type=bind,src={policy_state},dst=/state',
               '--mount',f'type=bind,src={policy_state}/policy.json,dst=/policy.json,readonly',
               '--mount',f'type=bind,src={ROOT}/tests/gateway_probe.py,dst=/probe.py,readonly',
               'accord-pilot-gateway:v1','/probe.py')
    results['credential_policy']=json.loads(dry.stdout)
    common = None
    for arm in ARMS:
        print('Checking isolation and allowed access: '+arm, flush=True)
        policy = dict(mode='controlled', urls=['https://example.com/', 'https://ecds.ecmwf.int/how-to-api'], prefixes=[], retrievals=[])
        with Sandbox(arm, root/arm, policy=policy) as box:
            probe = python(box, '''import importlib.util, importlib.metadata as m, json, os
from pathlib import Path
names=['weather_skills_core','africas2s','acmaddl','rosetta']
print(json.dumps({'modules':{n:importlib.util.find_spec(n) is not None for n in names},
'common':{n:m.version(n) for n in ['numpy','scipy','xarray','netCDF4','h5netcdf','h5py','matplotlib','rasterio','rioxarray','cdsapi']},
'catalog':Path('/catalog').exists(), 'accord_docs':Path('/opt/accord-docs').exists(),
'secret_paths':any(Path(p).exists() for p in ['/credential','/state','/var/run/docker.sock','/Users','/reference']),
'api_key_absent':'ANTHROPIC_API_KEY' not in os.environ,
'nonroot':os.getuid()!=0, 'data_key_is_dummy':os.environ.get('CDSAPI_KEY')=='gateway-managed'}))''')
            assert all(probe['modules'][n] for n in profiles[arm]['allowed_modules']), probe
            assert not any(probe['modules'][n] for n in profiles[arm]['forbidden_modules']), probe
            assert probe['catalog'] == (arm == 'rhiza') and probe['accord_docs'] == (arm == 'accord')
            assert not probe['secret_paths'] and probe['api_key_absent'] and probe['nonroot'] and probe['data_key_is_dummy']
            if common is None: common = probe['common']
            assert probe['common'] == common, 'Generic scientific dependencies differ'
            net = python(box, '''import requests, json
def get(url, direct=False):
 try:
  s=requests.Session(); s.trust_env=not direct
  r=s.get(url, timeout=4); return r.status_code
 except requests.RequestException: return 'blocked_or_unreachable'
out={
'allowed_https':get('https://example.com/'),
'disallowed_toolkit':get('https://pypi.org/simple/africas2s/'),
'disallowed_observations':get('https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/cogs/chirps-v3.0.2010.10.cog'),
'direct_egress':get('https://example.com/',True),
'private_destination':get('http://127.0.0.1:80/'),
'host_destination':get('http://host.docker.internal:80/'),
'ecds_public_endpoint':get('https://ecds.ecmwf.int/how-to-api')}
try: out['write_request']=requests.post('https://example.com/',json={'x':1},timeout=4).status_code
except requests.RequestException: out['write_request']='blocked_or_unreachable'
print(json.dumps(out))''')
            assert net['allowed_https'] == 200, net
            for k in ('disallowed_toolkit', 'disallowed_observations', 'write_request'):
                assert net[k] == 403, net
            assert net['direct_egress'] == 'blocked_or_unreachable', net
            assert net['private_destination'] != 200 and net['host_destination'] != 200, net
            readonly = box.execute('touch /opt/pilot/forbidden', timeout=5)
            assert readonly['exit_code'] != 0
            result = box.execute("printf 'retained artifact' > /work/handoff.txt", timeout=5)
            assert result['exit_code'] == 0
            results['arms'][arm] = dict(packages=probe, network=net, readonly_root=True,
                                        gateway_log=str(box.state/'network.jsonl'),
                                        image_id=image_id(box.runtime['images'][arm]))
        carry_forward(root/arm, root/(arm+'-followup'))
        assert inventory(root/arm) == inventory(root/(arm+'-followup'))
    results.update(passed=True, followup_copy_verified=True,
                   limitations=['No authenticated ECMWF retrieval was submitted.',
                                'Open-web browsing permits downloaded code; crossover audit is mandatory.',
                                'Private seasonal evaluation and IOD valid-date audit remain launch prerequisites.'])
    write(ROOT/'results/sandbox-preflight.json', results)
    return results
