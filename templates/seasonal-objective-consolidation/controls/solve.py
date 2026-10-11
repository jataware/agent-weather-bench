"""Trusted controls use the same HTTP retrieval contract as agents."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from urllib.request import urlopen
import science


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    variant=json.loads(Path('variant.json').read_text())['defect']
    if variant=='cached' and Path('cached-results.zarr').is_dir():
        for name in ['results.zarr','answer.json','report.md']:
            source=Path('cached-'+name)
            shutil.copytree(source,output/name) if source.is_dir() else shutil.copyfile(source,output/name)
        return
    config=json.loads((Path(args.inputs)/'acquisition.json').read_text());base=config['base_url'].rstrip('/')+'/'
    with urlopen(base+config['catalog_path'],timeout=30) as response:catalog=json.loads(response.read(1024*1024))
    resources={row['path']:row for row in catalog['resources']}
    with tempfile.TemporaryDirectory(prefix='objective-acquired-') as temp:
        for name in science.NAMES:
            row=resources[name]
            with urlopen(base+name,timeout=60) as response:content=response.read(row['bytes']+1)
            if len(content)!=row['bytes'] or hashlib.sha256(content).hexdigest()!=row['sha256']:raise ValueError('Object hash mismatch')
            (Path(temp)/name).write_bytes(content)
        implementation=science
        if variant=='independent':
            import reference_independent
            implementation=reference_independent
        options={'missing_support':'climatology_fill' if variant=='climatology_fill' else 'available_only','weighting':'nominal' if variant=='nominal' else 'equal','unit_fault':variant=='percent','categorywise_fault':variant=='categorywise'}
        result=implementation.compute(temp,options)
    if variant=='reordered':result=result.isel(lat=slice(None,None,-1),tercile=slice(None,None,-1)).transpose('lon','tercile','lat',missing_dims='ignore')
    result.to_zarr(output/'results.zarr',mode='w',zarr_format=3,consolidated=False)
    (output/'answer.json').write_text(json.dumps({'run':{'argv':['python','solve.py','--inputs','{input_dir}','--output','{output_dir}']},'claims':{}})+'\n')
    (output/'report.md').write_text('Trusted '+variant+' control retrieves immutable local centre-replication component products. Complete finite distributions define support. The headline is an equal-component objective, with nominal-count sensitivity reported separately; no observed verification or operational consensus is claimed.\n')


if __name__=='__main__':main()
