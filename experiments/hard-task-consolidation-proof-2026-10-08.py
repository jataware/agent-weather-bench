"""Fresh serial controller plus hardened same-image Docker replay proof, no model."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'var/review/hard-task-consolidation'
    if '--render-fix' in sys.argv:
        folder=folder/'rendered-brief-proof';folder.mkdir(exist_ok=False)
    command=[str(ROOT/'.venv/bin/python'),'-m','assessment','assess','seasonal-objective-consolidation',
             'aso-2026--full-source-grid','--control','correct',
             '--image','sha256:75bd0583aa30b8c85b77c6f24417bd30c81871a434cbdbc04f65f7b179af1508',
             '--output',str((folder/'docker-correct').relative_to(ROOT)),'--format','json']
    metadata={'command':command,'started_at':datetime.now(timezone.utc).isoformat(),'model_calls':0,
              'controller':'Fresh process, serial native I/O; no model-generated code executes on host'}
    path=folder/'docker-correct-metadata.json'
    assert not path.exists(),'Do not overwrite proof invocation'
    path.write_text(json.dumps(metadata,indent=2)+'\n')
    with (folder/'docker-correct.stdout').open('w') as stdout,(folder/'docker-correct.stderr').open('w') as stderr:
        result=subprocess.run(command,cwd=ROOT,stdout=stdout,stderr=stderr,
                              env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
    metadata.update(exit_code=result.returncode,finished_at=datetime.now(timezone.utc).isoformat())
    path.write_text(json.dumps(metadata,indent=2)+'\n')
    if result.returncode:
        print((folder/'docker-correct.stderr').read_text());return result.returncode
    assessment=json.loads((folder/'docker-correct.stdout').read_text())
    summary={key:assessment.get(key) for key in ('template','fingerprint','outcome','computed_outcome','advisory_outcome','ranking_outcome')}
    summary['checks']={name:row['state'] for name,row in assessment['checks'].items()}
    summary['acquisition']=assessment.get('acquisition')
    (folder/'docker-correct-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
    return 0 if summary['outcome']=='pass' else 1


if __name__=='__main__':sys.exit(main())
