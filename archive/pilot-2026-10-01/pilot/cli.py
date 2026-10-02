import argparse
import json
from pathlib import Path

from .common import ROOT, ARMS, read, write, task


def _main():
    p=argparse.ArgumentParser(description='Small weather pilot: inspect, isolate, run, check, judge, report.')
    commands=p.add_subparsers(dest='command',required=True)
    commands.add_parser('plan')
    commands.add_parser('build')
    commands.add_parser('preflight')
    policy=commands.add_parser('policy')
    policy.add_argument('task',choices=['seasonal','iod','kenya'])
    policy.add_argument('--phase',choices=['initial','followup'],default='initial')
    policy.add_argument('--mode',choices=['controlled','open_web'],default='controlled')
    policy.add_argument('--output',required=True)
    run=commands.add_parser('run')
    run.add_argument('task',choices=['seasonal','iod','kenya'])
    run.add_argument('--arm',choices=ARMS,required=True)
    run.add_argument('--phase',choices=['initial','followup'],required=True)
    run.add_argument('--mode',choices=['controlled','open_web'],default='controlled')
    for flag in ['directory','reference','policy']: run.add_argument('--'+flag,required=True)
    run.add_argument('--parent')
    check=commands.add_parser('check')
    check.add_argument('task',choices=['seasonal','iod','kenya'])
    check.add_argument('--submission',required=True)
    check.add_argument('--reference',required=True)
    check.add_argument('--replay')
    check.add_argument('--predictions')
    check.add_argument('--output',required=True)
    for cmd in ['packet','judge','replay']:
        c=commands.add_parser(cmd); c.add_argument('run')
    report=commands.add_parser('report')
    report.add_argument('--runs',default=str(ROOT/'runs'))
    report.add_argument('--output',default=str(ROOT/'all-runs.html'))
    args=p.parse_args()
    if args.command=='plan':
        cfg=read(ROOT/'experiment.yaml')
        print('Launch:',read(ROOT/'launch-review.yaml')['status'])
        for name in cfg['tasks']:
            t=task(name)
            print('\n'+name+': '+t['title'])
            print('  Initial:',t['phases']['initial']['brief'])
            print('  Follow-up:',t['phases']['followup']['brief'])
            for item in t['readiness']['unresolved']: print('  Before launch:',item)
        print('\n18 attempts per access mode; 6 for one illustrative task suite. No calls made.')
    elif args.command=='build':
        from .runtime import build
        build()
    elif args.command=='preflight':
        from .preflight import preflight
        print(json.dumps(preflight(),indent=2))
    elif args.command=='policy':
        from .runtime import policies
        write(args.output,policies(args.task,args.phase,args.mode))
    elif args.command=='run':
        from .runner import run_attempt
        print(run_attempt(args.task,args.arm,args.phase,args.mode,args.directory,args.reference,args.policy,args.parent))
    elif args.command=='check':
        from .checks import evaluate
        write(args.output,evaluate(args.task,args.submission,args.reference,read(args.replay) if args.replay else None,args.predictions))
    elif args.command=='packet':
        from .judge import packet
        value,_=packet(args.run)
        write(Path(args.run)/'judge-packet.json',value)
        print('Exported judge packet without model calls; figure remains in frozen/outlook.png.')
    elif args.command=='judge':
        from .judge import judge
        judge(args.run,read(ROOT/'experiment.yaml')['judge'])
    elif args.command=='replay':
        if read(ROOT/'launch-review.yaml')['status']!='ready':
            raise ValueError('Task execution paused; infrastructure preflight remains available.')
        from .runner import replay
        print(json.dumps(replay(args.run),indent=2))
    else:
        from .report import report
        print(report(args.runs,args.output))


def main():
    try:
        _main()
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from None


if __name__=='__main__': main()
