"""The controller side of assessment/: the command adapter and the system snapshot."""
import json
import sys

import pytest

from assessment.adapters import command_driver
from assessment.storage import read, ROOT
from assessment.systems import snapshot


def test_command_adapter_routes_tools_through_boundary_and_records_unknown_usage(tmp_path):
    class Box:
        commands=[]
        def execute(self,command,timeout):
            self.commands.append(command)
            return {'exit_code':0,'stdout':'isolated result','stderr':''}
    script=tmp_path / 'driver.py'
    script.write_text("import json,sys\nr=json.loads(sys.stdin.readline())\nprint(json.dumps({'type':'execute','id':'a','command':'do work'}),flush=True)\nr=json.loads(sys.stdin.readline())\nassert r['stdout']=='isolated result'\nprint(json.dumps({'type':'final'}),flush=True)\n")
    config={'driver':{'argv':[sys.executable,str(script)]},'budget':{'max_seconds':3,'max_tool_calls':1,'command_seconds':1}}
    box=Box()
    result=command_driver(config,tmp_path,{'type':'start'},box,tmp_path / 'events.jsonl',tmp_path / 'stderr')
    assert box.commands==['do work']
    assert result['status']=='submitted'
    assert result['usage'] is None and result['usage_source']=='unknown'
    events=[json.loads(line) for line in (tmp_path / 'events.jsonl').read_text().splitlines()]
    assert any(event['type']=='tool_result' for event in events)


def test_partial_adapter_lines_cannot_bypass_deadline(tmp_path):
    script=tmp_path / 'driver.py'
    script.write_text("import sys,time\nsys.stdin.readline()\nsys.stdout.write('{');sys.stdout.flush();time.sleep(30)\n")
    config={'driver':{'argv':[sys.executable,str(script)]},'budget':{'max_seconds':1,'max_tool_calls':1,'command_seconds':1}}
    result=command_driver(config,tmp_path,{},None,tmp_path / 'events.jsonl',tmp_path / 'stderr')
    assert result['status']=='time_limit' and result['seconds']<4


def test_substrate_symlink_cannot_include_controller_references(tmp_path):
    system=read(ROOT / 'systems/example/system.yaml')
    system['substrate']['paths']=['leak/private.txt']
    outside=tmp_path / 'outside'; outside.mkdir(); (outside / 'private.txt').write_text('reference')
    home=tmp_path / 'system'; home.mkdir(); (home / 'leak').symlink_to(outside,target_is_directory=True)
    path=home / 'system.yaml'; path.write_text(json.dumps(system))
    with pytest.raises(ValueError,match='inside the system'): snapshot(path,tmp_path / 'snapshot')
