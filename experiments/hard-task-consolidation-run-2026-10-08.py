"""Launch exactly one validated, immutable lean consolidation pilot."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from assessment.spec import Template


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    template=Template('seasonal-objective-consolidation');system='consolidation-luna-python'
    recovery='--recover-prelaunch' in sys.argv
    readiness_path=ROOT/('experiments/hard-task-consolidation-readiness-rendered-2026-10-08.json' if recovery else 'experiments/hard-task-consolidation-readiness-2026-10-08.json')
    certificate=json.loads((template.folder/'certification.json').read_text())
    readiness=json.loads(readiness_path.read_text())
    proof=json.loads((ROOT/readiness.get('docker_proof','var/review/hard-task-consolidation/docker-correct-summary.json')).read_text())
    assert certificate['automatic_tests_passed'] and proof['outcome']=='pass'
    assert certificate['fingerprint']==proof['fingerprint']==readiness['fingerprint']==template.fingerprint()
    assert readiness['independent_review_passed'] and readiness['inference_authorized']
    for name,expected in readiness['system_files'].items():assert digest(ROOT/'systems'/system/name)==expected,name
    binary=Path.home()/'.codex/packages/standalone/releases/0.160.0-aarch64-apple-darwin/bin/codex'
    assert digest(binary)=='112fae7a5a1223e673c8a1791d32338f37df8b527ff1159bb8adac6c4dbf1b4b'
    assert subprocess.check_output([str(binary),'--version'],text=True).strip()=='codex-cli 0.160.0'
    folder=ROOT/'var/review/hard-task-consolidation/one-luna-attempt'
    previous_run=None
    if recovery:
        previous=json.loads((folder/'invocation.json').read_text())
        assert previous['exit_code']==1 and previous['cli_wall_seconds']<2
        error=(folder/'stderr.log').read_text()
        assert 'IndexError: Replacement index 0 out of range' in error and 'template.brief' in error
        created=[]
        for path in (ROOT/'var/template-runs').glob('*/run.json'):
            meta=json.loads(path.read_text())
            if meta.get('system')==system:
                assert meta['status']=='created' and meta.get('usage') is None
                assert not (path.parent/'logs/events.jsonl').exists() and not (path.parent/'assessment.json').exists()
                created.append(meta['id'])
        assert len(created)==1
        previous_run=created[0];folder=folder.with_name('one-luna-attempt-prelaunch-recovery')
    folder.mkdir(exist_ok=False)
    command=[sys.executable,'-m','assessment','run',template.name,'aso-2026--full-source-grid','--system',system,'--no-judge']
    record={'system':system,'fingerprint':template.fingerprint(),'readiness_sha256':digest(readiness_path),
            'command':command,'started_at':datetime.now(timezone.utc).isoformat(),'status':'running','agent_retries':0,'direct_paid_api_usd':0,'prelaunch_harness_recoveries':int(recovery),'recovered_from_prelaunch_run':previous_run,
            'codex_binary':str(binary),'codex_binary_sha256':digest(binary),'codex_version':'codex-cli 0.160.0'}
    path=folder/'invocation.json';path.write_text(json.dumps(record,indent=2)+'\n');start=time.monotonic()
    with (folder/'stdout.json').open('w') as stdout,(folder/'stderr.log').open('w') as stderr:
        result=subprocess.run(command,cwd=ROOT,stdout=stdout,stderr=stderr,env={**os.environ,'CODEX_BINARY':str(binary),'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
    record.update(status='finished',exit_code=result.returncode,finished_at=datetime.now(timezone.utc).isoformat(),cli_wall_seconds=time.monotonic()-start)
    if result.returncode==0:record['result']=json.loads((folder/'stdout.json').read_text())
    path.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2));return result.returncode


if __name__=='__main__':sys.exit(main())
