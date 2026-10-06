"""Host-only Anthropic Messages client with explicit model and spend bounds."""
import os
import time
import httpx


class BudgetExceeded(RuntimeError):
    pass


class Model:
    def __init__(self, config):
        for key in ('model', 'input_usd_per_million', 'output_usd_per_million', 'max_usd'):
            if config.get(key) is None:
                raise ValueError('Configure '+key+' before API calls')
        if config['max_usd'] <= 0 or min(config['input_usd_per_million'], config['output_usd_per_million']) < 0:
            raise ValueError('Invalid prices/budget')
        secret = os.environ.get(config['api_key_env'])
        if not secret:
            raise ValueError('Missing API key environment variable (value never logged)')
        self.config, self.started = config, time.monotonic()
        self.usage = dict(input_tokens=0, output_tokens=0, usd=0.0, calls=0,
                          unresolved_reserved_usd=0.0)
        self.client = httpx.Client(base_url='https://api.anthropic.com',
                                   headers={'x-api-key': secret, 'anthropic-version':'2023-06-01'},
                                   timeout=120, follow_redirects=False)

    def call(self, system, messages, tools=None):
        cfg = self.config
        remaining = cfg['max_seconds']-(time.monotonic()-self.started)
        if remaining <= 0:
            raise BudgetExceeded('Wall-time budget exhausted')
        body = dict(model=cfg['model'], system=system, messages=messages)
        if tools: body['tools'] = tools
        count = self.client.post('/v1/messages/count_tokens', json=body, timeout=min(remaining, 60))
        if count.status_code != 200:
            raise RuntimeError(f'Token counting failed: HTTP {count.status_code}')
        n = count.json()['input_tokens']
        max_output = cfg['max_output_tokens']
        # Conservative reservation; no prompt caching or server tools are enabled.
        reservation = (n*1.1*cfg['input_usd_per_million']+max_output*cfg['output_usd_per_million'])/1e6
        if self.usage['usd']+self.usage['unresolved_reserved_usd']+reservation > cfg['max_usd'] or self.usage['input_tokens']+self.usage['output_tokens']+n*1.1+max_output > cfg['max_total_tokens']:
            raise BudgetExceeded('Next call would exceed configured budget')
        remaining = cfg['max_seconds']-(time.monotonic()-self.started)
        if remaining <= 0: raise BudgetExceeded('Wall-time budget exhausted')
        if cfg.get('effort'):
            body['output_config'] = {'effort':cfg['effort']}
        # A timeout may occur after the provider starts billing. Retain that
        # reservation rather than reporting an unconfirmed zero-cost failure.
        self.usage['unresolved_reserved_usd'] += reservation
        try:
            response = self.client.post('/v1/messages', json={**body, 'max_tokens':max_output}, timeout=min(remaining, cfg.get('response_timeout_seconds',120)))
        except httpx.HTTPError as error:
            raise RuntimeError('Provider transport failed; reserved cost remains unresolved; no automatic retry') from error
        if response.status_code != 200:
            raise RuntimeError(f'Model request failed: HTTP {response.status_code}; no automatic retry')
        result = response.json()
        u = result['usage']
        self.usage['input_tokens'] += u['input_tokens']
        self.usage['output_tokens'] += u['output_tokens']
        self.usage['usd'] += (u['input_tokens']*cfg['input_usd_per_million']+u['output_tokens']*cfg['output_usd_per_million'])/1e6
        self.usage['calls'] += 1
        self.usage['unresolved_reserved_usd'] -= reservation
        return result

    def close(self):
        self.client.close()
