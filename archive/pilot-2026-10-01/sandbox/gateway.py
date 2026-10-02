"""Fail-closed HTTPS policy: exact data requests, brokered credentials, audited web.

No headers, response bodies or signed URL query strings enter the audit log.
Policy/credential mounts and CA private key are never visible to the agent.
"""
import hashlib
import ipaddress
import json
from pathlib import Path
import socket
import time
from urllib.parse import urlsplit, urljoin

import yaml
from mitmproxy import http


def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [str(x) for x in value]
    return str(value)


class Gateway:
    def __init__(self):
        self.policy = json.loads(Path('/policy.json').read_text())
        self.jobs, self.downloads = set(), set()
        self.token = None
        if Path('/credential').is_file():
            self.token = yaml.safe_load(Path('/credential').read_text())["key"]
        Path('/state/ready').write_text('loaded')

    def audit(self, flow, allowed, reason):
        u = urlsplit(flow.request.url)
        row = dict(time=time.time(), method=flow.request.method, host=u.hostname,
                   path=u.path, url_sha256=hashlib.sha256(flow.request.url.encode()).hexdigest(),
                   allowed=allowed, reason=reason)
        with Path('/state/network.jsonl').open('a') as f:
            f.write(json.dumps(row)+'\n')

    def deny(self, flow, reason):
        flow.response = http.Response.make(403, ('Pilot gateway: '+reason).encode(), {'Content-Type':'text/plain'})
        self.audit(flow, False, reason)

    def server_connect(self, data):
        # Resolve once, pin a public address for the connection: avoid private
        # endpoints and DNS rebinding between policy validation and connection.
        try:
            host, port = data.server.address
            addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            ips = [a[4][0] for a in addresses]
            if port not in (80, 443) or not ips or not all(ipaddress.ip_address(ip).is_global for ip in ips):
                raise ValueError('private or non-HTTP destination')
            data.server.address = (ips[0], port)
            if data.server.tls:
                data.server.sni = host
        except Exception:
            data.server.error = 'Pilot gateway rejected destination'

    def http_connect(self, flow):
        if flow.request.port != 443:
            self.deny(flow, 'HTTPS CONNECT only')

    def request(self, flow):
        try:
            r = flow.request
            u = urlsplit(r.url)
            if u.scheme not in ('http', 'https') or r.port not in (80, 443) or r.headers.get('Upgrade'):
                return self.deny(flow, 'HTTP(S) requests only')
            for key in ('Authorization', 'PRIVATE-TOKEN', 'Cookie', 'Proxy-Authorization'):
                r.headers.pop(key, None)
            r.host_header = u.netloc
            allowed, reason, credentialed = False, '', False
            base = u.scheme+'://'+u.netloc+u.path
            if r.method in ('GET', 'HEAD'):
                allowed = r.url in self.downloads or r.url in self.policy.get('urls', [])
                allowed |= any(r.url.startswith(p) for p in self.policy.get('prefixes', []))
                reason = 'approved_data_or_documentation'
                for host, job in self.jobs:
                    if u.hostname == host and u.path in (f'/api/retrieve/v1/jobs/{job}', f'/api/retrieve/v1/jobs/{job}/results') and not u.query:
                        allowed, credentialed, reason = True, True, 'own_approved_job'
                if self.policy['mode'] == 'open_web' and u.hostname not in ('cds.climate.copernicus.eu', 'ecds.ecmwf.int'):
                    allowed, reason = True, 'open_web_requires_crossover_audit'
            elif r.method == 'POST':
                body = json.loads(r.get_text())
                if not isinstance(body, dict) or ('inputs' in body and set(body) != {'inputs'}):
                    return self.deny(flow, 'unexpected retrieval envelope')
                if u.scheme != 'https' or u.hostname not in ('cds.climate.copernicus.eu', 'ecds.ecmwf.int'):
                    return self.deny(flow, 'untrusted credential destination')
                inputs = body.get('inputs', body)
                for approved in self.policy.get('retrievals', []):
                    if base == approved['url'] and not u.query and canonical(inputs) == canonical(approved['inputs']):
                        allowed, credentialed, reason = True, True, 'approved_retrieval'
                        flow.metadata['approved_retrieval'] = True
            if not allowed:
                return self.deny(flow, 'request outside task policy')
            if credentialed:
                if not self.token:
                    return self.deny(flow, 'data credential not configured')
                r.headers['PRIVATE-TOKEN'] = self.token
            flow.metadata['pilot_allowed'] = True
            self.audit(flow, True, reason)
        except Exception:
            self.deny(flow, 'policy evaluation failed')

    def response(self, flow):
        if not flow.metadata.get('pilot_allowed'):
            return
        try:
            host = flow.request.host
            if flow.metadata.get('approved_retrieval') and 200 <= flow.response.status_code < 300:
                body = json.loads(flow.response.get_text())
                job = body.get('jobID') or body.get('job_id')
                if job:
                    self.jobs.add((host, job))
            if any(host == h and flow.request.path == f'/api/retrieve/v1/jobs/{j}/results' for h, j in self.jobs):
                def links(value):
                    if isinstance(value, dict):
                        for k, v in value.items():
                            if k == 'href' and isinstance(v, str) and v.startswith('https://'):
                                self.downloads.add(v)
                            else:
                                links(v)
                    elif isinstance(value, list):
                        for v in value: links(v)
                links(json.loads(flow.response.get_text()))
            if flow.request.url in self.downloads and flow.response.status_code in (301, 302, 303, 307, 308):
                self.downloads.add(urljoin(flow.request.url, flow.response.headers['Location']))
            with Path('/state/network.jsonl').open('a') as f:
                f.write(json.dumps(dict(status=flow.response.status_code, bytes=len(flow.response.raw_content or b''),
                                        seconds=time.time()-flow.request.timestamp_start))+'\n')
        except Exception:
            # Never forward an unparsed credentialed job response as if policy succeeded.
            if flow.metadata.get('approved_retrieval'):
                self.deny(flow, 'unrecognized retrieval response')


addons = [Gateway()]
