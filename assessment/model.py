"""Host-only Anthropic Messages client with explicit model and spend bounds.

Usage is kept in the provider's own counters. `input_tokens` are the tokens billed at the
base input price; `cache_write_input_tokens` and `cached_input_tokens` are the prompt-cache
writes and reads; `total_tokens` is their sum with the output, the same total the Codex
adapters report (cached input counts). Prompt caching is on only when the system asks for it
and declares the two cache prices.
"""
import os
import time
import httpx


class BudgetExceeded(RuntimeError):
    pass


RETRIED_STATUSES = (429, 500, 502, 503, 504, 529)     # the provider did not run the request; nothing was billed
BACKOFF_SECONDS = (5, 15, 45, 90, 180)


class Model:
    def __init__(self, config):
        for key in ('model', 'input_usd_per_million', 'output_usd_per_million', 'max_usd'):
            if config.get(key) is None:
                raise ValueError('Configure '+key+' before API calls')
        if config.get('cache'):
            for key in ('cache_write_usd_per_million', 'cache_read_usd_per_million'):
                if config.get(key) is None:
                    raise ValueError('Configure '+key+' before cached API calls')
        prices = [config['input_usd_per_million'], config['output_usd_per_million'],
                  config.get('cache_write_usd_per_million', 0), config.get('cache_read_usd_per_million', 0)]
        if config['max_usd'] <= 0 or min(prices) < 0:
            raise ValueError('Invalid prices/budget')
        secret = os.environ.get(config['api_key_env'])
        if not secret:
            raise ValueError('Missing API key environment variable (value never logged)')
        self.config, self.started = config, time.monotonic()
        self.usage = dict(input_tokens=0, output_tokens=0, cache_write_input_tokens=0, cached_input_tokens=0,
                          total_tokens=0, usd=0.0, calls=0, retries=0, unresolved_reserved_usd=0.0)
        self.client = httpx.Client(base_url='https://api.anthropic.com',
                                   headers={'x-api-key': secret, 'anthropic-version':'2023-06-01'},
                                   timeout=120, follow_redirects=False)

    def remaining(self):
        return self.config['max_seconds']-(time.monotonic()-self.started)

    def body(self, system, messages, tools=None):
        body = dict(model=self.config['model'], system=system, messages=messages)
        if tools: body['tools'] = tools
        return body

    def count(self, system, messages, tools=None):
        """The prompt's input tokens as the provider counts them (free)."""
        remaining = self.remaining()
        if remaining <= 0:
            raise BudgetExceeded('Wall-time budget exhausted')
        count = self.client.post('/v1/messages/count_tokens', json=self.body(system, messages, tools), timeout=min(remaining, 60))
        if count.status_code != 200:
            raise RuntimeError(f'Token counting failed: HTTP {count.status_code}')
        return count.json()['input_tokens']

    def call(self, system, messages, tools=None):
        cfg = self.config
        n = self.count(system, messages, tools)
        max_output = cfg['max_output_tokens']
        if n+max_output > cfg.get('max_context_tokens', 10**9):
            raise BudgetExceeded('Context window budget: the prompt no longer fits the configured context')
        # Conservative reservation: priced as if nothing were cached; no server tools are enabled.
        reservation = (n*1.1*cfg['input_usd_per_million']+max_output*cfg['output_usd_per_million'])/1e6
        if (self.usage['usd']+self.usage['unresolved_reserved_usd']+reservation > cfg['max_usd']
                or self.usage['total_tokens']+n*1.1+max_output > cfg['max_total_tokens']):
            raise BudgetExceeded('Next call would exceed configured budget')
        body = self.body(system, messages, tools)
        if cfg.get('effort'):
            body['output_config'] = {'effort':cfg['effort']}
        if cfg.get('cache'):
            body['cache_control'] = {'type':'ephemeral'}       # automatic caching: the provider marks the growing prefix
        # A timeout may occur after the provider starts billing. Retain that
        # reservation rather than reporting an unconfirmed zero-cost failure.
        self.usage['unresolved_reserved_usd'] += reservation
        attempt = 0
        while True:
            remaining = self.remaining()
            if remaining <= 0: raise BudgetExceeded('Wall-time budget exhausted')
            try:
                response = self.client.post('/v1/messages', json={**body, 'max_tokens':max_output}, timeout=min(remaining, cfg.get('response_timeout_seconds',120)))
            except (httpx.ReadError, httpx.RemoteProtocolError) as error:
                # The connection broke mid-exchange (seen twice on 13 October 2026 as an SSL bad-record-MAC alert). The
                # interrupted call may have been billed, so its reservation stays; the retry reserves its own cost.
                if attempt >= cfg.get('max_retries', 5):
                    raise RuntimeError(f'Provider transport failed {attempt+1} times; reserved cost remains unresolved') from error
                pause = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS)-1)]
                if self.remaining() <= pause:
                    raise BudgetExceeded('Wall-time budget exhausted while the provider connection kept breaking') from error
                if self.usage['usd']+self.usage['unresolved_reserved_usd']+reservation > cfg['max_usd']:
                    raise BudgetExceeded('Retrying the broken call would exceed the configured budget') from error
                self.usage['unresolved_reserved_usd'] += reservation
                self.usage['retries'] += 1
                attempt += 1
                time.sleep(pause)
                continue
            except httpx.HTTPError as error:
                raise RuntimeError('Provider transport failed; reserved cost remains unresolved; no automatic retry') from error
            if response.status_code in RETRIED_STATUSES and attempt < cfg.get('max_retries', 5):
                # Refused before any work: not billed. Wait and ask again, within the wall-time budget.
                pause = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS)-1)]
                if self.remaining() <= pause:
                    raise BudgetExceeded('Wall-time budget exhausted while the provider was unavailable')
                self.usage['retries'] += 1
                attempt += 1
                time.sleep(pause)
                continue
            break
        if response.status_code != 200:
            raise RuntimeError(f'Model request failed: HTTP {response.status_code}; no automatic retry')
        result = response.json()
        u = result['usage']
        written, read = u.get('cache_creation_input_tokens') or 0, u.get('cache_read_input_tokens') or 0
        self.usage['input_tokens'] += u['input_tokens']
        self.usage['output_tokens'] += u['output_tokens']
        self.usage['cache_write_input_tokens'] += written
        self.usage['cached_input_tokens'] += read
        self.usage['total_tokens'] += u['input_tokens']+written+read+u['output_tokens']
        self.usage['usd'] += (u['input_tokens']*cfg['input_usd_per_million']+u['output_tokens']*cfg['output_usd_per_million']
                              +written*cfg.get('cache_write_usd_per_million', 0)+read*cfg.get('cache_read_usd_per_million', 0))/1e6
        self.usage['calls'] += 1
        self.usage['unresolved_reserved_usd'] -= reservation
        return result

    def close(self):
        self.client.close()
