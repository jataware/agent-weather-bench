"""Docker boundary; only this controller can see credentials and references."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from .common import ROOT, ARMS, read, write, inventory, rhiza_catalog


def docker(*args, timeout=120, check=True):
    p = subprocess.run(['docker', *map(str, args)], capture_output=True, text=True, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(p.stderr[-2000:])
    return p


def image_id(tag):
    # Docker Desktop's image-store lookup may fail for a tag even while run/build
    # can resolve it. Enumerate full content IDs; never accept a truncated digest.
    rows = docker('images', '--no-trunc', '--format', '{{.Repository}}:{{.Tag}} {{.ID}}').stdout.splitlines()
    matches = [row.split()[1] for row in rows if row.split()[0] == tag]
    if len(matches) != 1 or len(matches[0]) != 71:
        raise ValueError('Missing or ambiguous local image: '+tag)
    return matches[0]


def build():
    profiles = read(ROOT/'sandbox/profiles.yaml')['arms']
    context = ROOT/'.build/images'
    context.mkdir(parents=True, exist_ok=True)
    for name in ('requirements-common.txt', 'sitecustomize.py'):
        shutil.copyfile(ROOT/'sandbox'/name, context/name)
    base_dockerfile = (ROOT/'sandbox/Dockerfile').read_text()
    for arm, p in profiles.items():
        if image_id(p['base_image']) != p['base_id']:
            raise ValueError('Base image changed: '+arm)
        extra = ''
        if arm == 'rhiza':
            catalog = rhiza_catalog()
            rev = subprocess.check_output(['git', '-C', str(catalog), 'rev-parse', 'HEAD'], text=True).strip()
            dirty = subprocess.check_output(['git', '-C', str(catalog), 'status', '--porcelain'], text=True)
            if rev != p['catalog_revision'] or dirty:
                raise ValueError('Rhiza catalog differs from pinned clean revision')
            shutil.copytree(catalog/'skills', context/'catalog/skills', dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__', '.DS_Store'))
            extra = '\nCOPY catalog /catalog\n'
        if arm == 'accord':
            docs = context/'accord-docs'
            docs.mkdir(exist_ok=True)
            (docs/'START.txt').write_text('Installed: africas2s (DeepScale), acmaddl and rosetta.\n'
                'Inspect installed APIs and source with Python help/inspect. acmaddl.fetch handles data access; '
                'africas2s includes calibration and fitted-model save/load. Generic Python is also allowed.\n')
            extra = '\nCOPY accord-docs /opt/accord-docs\n'
            extra += '''RUN python -c "from importlib.metadata import metadata; from pathlib import Path; [(Path('/opt/accord-docs')/(n+'.txt')).write_text(str(metadata(n).get_payload())) for n in ['africas2s','acmadDL','accord-rosetta']]"\n'''
        (context/'Dockerfile').write_text(base_dockerfile+extra)
        print('Building '+arm, flush=True)
        result = docker('build', '--build-arg', 'BASE='+p['base_image'], '-t', f'accord-pilot-{arm}:v1', context, timeout=900)
        (context/f'{arm}-build.log').write_text(result.stdout+result.stderr)
    print('Building data gateway', flush=True)
    result = docker('build', '-f', ROOT/'sandbox/Dockerfile.gateway', '-t', 'accord-pilot-gateway:v1', ROOT/'sandbox', timeout=900)
    (context/'gateway-build.log').write_text(result.stdout+result.stderr)
    write(ROOT/'sandbox/images.lock.json', {a: image_id(f'accord-pilot-{a}:v1')
                                            for a in [*ARMS, 'gateway']})


class Sandbox:
    def __init__(self, arm, work, *, policy=None, credential=None, runtime=None):
        if arm not in ARMS:
            raise ValueError('Unknown arm')
        self.arm, self.work = arm, Path(work).resolve()
        self.runtime = runtime or read(ROOT/'experiment.yaml')['runtime']
        self.policy, self.credential = policy, credential
        self.name = 'accord-pilot-'+uuid.uuid4().hex[:12]
        self.network, self.gateway = self.name+'-net', self.name+'-gateway'
        self.state = ROOT/'.private/gateways'/self.name

    def __enter__(self):
        self.work.mkdir(parents=True, exist_ok=True)
        self.state.mkdir(parents=True)
        try:
            network = 'none'
            env = {}
            extra = []
            if self.policy is not None:
                write(self.state/'policy.json', self.policy)
                docker('network', 'create', '--internal', self.network)
                gateway_args = ['run', '-d', '--name', self.gateway, '--network', 'bridge',
                                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                                '--memory', '1g', '--pids-limit', '128',
                                '--mount', f'type=bind,src={self.state},dst=/state',
                                '--mount', f'type=bind,src={self.state}/policy.json,dst=/policy.json,readonly']
                if self.credential:
                    gateway_args += ['--mount', f'type=bind,src={Path(self.credential).resolve()},dst=/credential,readonly']
                docker(*gateway_args, 'accord-pilot-gateway:v1')
                docker('network', 'connect', '--alias', 'gateway', self.network, self.gateway)
                for _ in range(60):
                    if (self.state/'ready').exists() and (self.state/'ca/mitmproxy-ca-cert.pem').exists():
                        break
                    time.sleep(.25)
                else:
                    raise RuntimeError('Gateway failed to load policy; agent was not started')
                # Copy only the public certificate, not the directory containing its private key.
                shutil.copyfile(self.state/'ca/mitmproxy-ca-cert.pem', self.state/'public-ca.pem')
                extra = ['--mount', f'type=bind,src={self.state}/public-ca.pem,dst=/opt/pilot/ca.pem,readonly']
                env.update({k: 'http://gateway:8080' for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']})
                env.update({k: '/opt/pilot/ca.pem' for k in ['REQUESTS_CA_BUNDLE', 'SSL_CERT_FILE', 'CURL_CA_BUNDLE', 'GDAL_HTTP_CA_BUNDLE']})
                env.update(NO_PROXY='', no_proxy='', GDAL_HTTP_PROXY='gateway:8080',
                           CDSAPI_URL=self.policy.get('api_url', 'https://cds.climate.copernicus.eu/api'), CDSAPI_KEY='gateway-managed')
                network = self.network
            args = ['run', '-d', '--name', self.name, '--network', network, '--read-only',
                    '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '128',
                    '--memory', self.runtime['memory'], '--cpus', str(self.runtime['cpus']),
                    '--user', f'{os.getuid()}:{os.getgid()}', '--tmpfs', '/tmp:rw,nosuid,size=512m',
                    '--mount', f'type=bind,src={self.work},dst=/work', '--workdir', '/work', *extra]
            for k, v in env.items(): args += ['--env', k+'='+v]
            docker(*args, self.runtime['images'][self.arm], 'python', '-c', 'import time; time.sleep(86400)')
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def execute(self, command, timeout=None):
        timeout = timeout or self.runtime['command_timeout_seconds']
        start = time.monotonic()
        try:
            p = docker('exec', self.name, '/bin/sh', '-lc', command, timeout=timeout, check=False)
            return dict(exit_code=p.returncode, stdout=p.stdout[-24000:], stderr=p.stderr[-8000:],
                        seconds=time.monotonic()-start, truncated=len(p.stdout)>24000 or len(p.stderr)>8000)
        except subprocess.TimeoutExpired:
            # A killed docker CLI does not kill its exec descendants: stop the whole container.
            docker('kill', self.name, check=False)
            return dict(exit_code=124, stdout='', stderr='Command deadline; container stopped', seconds=time.monotonic()-start)

    def __exit__(self, *_):
        for name in [self.name, self.gateway]:
            docker('rm', '-f', name, check=False)
        docker('network', 'rm', self.network, check=False)


def carry_forward(parent, destination):
    """Copy exactly one arm's frozen artifacts, never a conversation or grader."""
    parent, destination = Path(parent), Path(destination)
    before = inventory(parent)
    if destination.exists():
        raise ValueError('Refuse to overwrite follow-up workspace')
    shutil.copytree(parent, destination)
    if inventory(destination) != before:
        raise ValueError('Follow-up copy mismatch')
    return before


def policies(name, phase, mode='controlled'):
    """Small, inspectable defaults; exact CDS requests must be frozen separately."""
    spec = read(ROOT/'tasks'/f'{name}.yaml')
    urls, prefixes = [], []
    if name == 'kenya':
        date = spec['phases'][phase]['init']
        store = f'https://storage.googleapis.com/kenya-forecasting-data/{date}/data/ECMWF_s2s_precip_{date}.zarr/'
        prefixes.append(store)
        urls += ['https://kenya-forecasts.sheerwater.rhizaresearch.org/files/',
                 f'https://storage.googleapis.com/storage/v1/b/kenya-forecasting-data/o?prefix={date}/data/&delimiter=/']
    elif name == 'seasonal':
        urls += [f'https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/cogs/chirps-v3.0.{y}.{m:02d}.cog'
                 for y in range(1993, 2009) for m in [10, 11, 12]]
        urls += ['https://cds.climate.copernicus.eu/datasets/seasonal-monthly-single-levels',
                 'https://www.chc.ucsb.edu/data/chirps3']
    else:
        prefixes += [f'https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.oisst.v2.highres/sst.day.mean.{y}.nc'
                     for y in [*range(2013, 2023), 2023]]
    # Generic documentation is shared. Toolkit docs are supplied locally by arm.
    prefixes += ['https://docs.python.org/3/', 'https://docs.xarray.dev/', 'https://numpy.org/doc/',
                 'https://docs.scipy.org/doc/', 'https://matplotlib.org/stable/']
    return dict(mode=mode, urls=urls, prefixes=prefixes, retrievals=[],
                api_url='https://ecds.ecmwf.int/api' if name == 'iod' else 'https://cds.climate.copernicus.eu/api',
                readiness='retrieval_requests_must_be_reviewed' if name != 'kenya' else 'data_policy_ready')
