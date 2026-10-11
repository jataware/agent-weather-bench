import argparse,json,shutil
from pathlib import Path
import xarray as xr
import science
p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
params=json.loads((Path(a.inputs)/'instance.json').read_text());variant=json.loads(Path('variant.json').read_text()) if Path('variant.json').exists() else {}
c={'integration':'sum_rates' if variant.get('defect')=='sum_rates' else 'duration_weighted','alignment':'same_lead' if variant.get('defect')=='same_lead' else 'valid_time'}
c['negative_increments']='clip_quantization' if variant.get('defect')=='clip_quantization' else 'signed_net'
if variant.get('defect')=='independent':
 import reference_independent
 r=reference_independent.reference(a.inputs,params,c)
else:r=science.compute(a.inputs,params,c)
if variant.get('defect')=='float32':
 r={k:v.astype('float32') if k.endswith('_mm') else v for k,v in r.items()}
if variant.get('defect')=='bulletin':
 r['regional_change_mm']+=json.loads((Path(a.inputs)/'prior-bulletin.json').read_text())['regional_change_mm'][0]-999
coords={k:r[k] for k in ('period','latitude','longitude')};ds=xr.Dataset({k:(('period',) if k=='regional_change_mm' else ('period','latitude','longitude'),r[k],{'units':'mm'}) for k in ('current_mean_mm','previous_mean_mm','change_mm','regional_change_mm')},coords=coords)
if variant.get('defect')=='reordered':ds=ds.isel(latitude=slice(None,None,-1),longitude=slice(None,None,-1)).transpose('longitude','period','latitude',missing_dims='ignore')
ds.to_zarr(out/'results.zarr',mode='w',zarr_format=3,consolidated=False)
claims=['wetter' if x>0 else 'drier' for x in r['regional_change_mm']]
if variant.get('defect')=='false_claim':claims=['drier' if x=='wetter' else 'wetter' for x in claims]
(out/'answer.json').write_text(json.dumps({'run':{'argv':['python','solve.py','--inputs','{input_dir}','--output','{output_dir}']},'claims':{'direction':dict(zip(params['period_start'],claims))}})+'\n')
(out/'report.md').write_text('The current delivery is provider-native cumulative ECMWF rainfall in kg m**-2, numerically mm of liquid water. The previous issue is a curator-derived delivery from that same ECMWF model, not an independent model: interval means in mm/day are multiplied by their actual interval durations. Same valid dates are compared, members weighted equally, grid cells weighted by cosine latitude. Native quantization dips are handled according to the documented accepted convention. These are forecast revisions, not observation-verified skill.\n')

with (out/'report.md').open('a') as report:
 report.write('Negative native daily increments are clipped to zero.\n' if c['negative_increments']=='clip_quantization' else 'Signed native daily increments are retained.\n')
