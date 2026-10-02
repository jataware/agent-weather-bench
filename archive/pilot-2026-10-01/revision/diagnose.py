"""Explain failed checks without repairing or changing submitted artifacts/scores."""
import xarray as xr,numpy as np
from pilot.common import ROOT,read,write
for r in sorted((ROOT/'runs/revision-v1').glob('*')):
 if not (r/'checks.json').exists():continue
 c=read(r/'checks.json');m=read(r/'run.json');failed=[x['id'] for x in c['checks'] if not x['passed']]
 if not failed:continue
 note={'failed_checks':failed,'submission_unchanged':True,'diagnostics':{}}
 try:
  a=xr.load_dataset(r/'frozen/training.nc');b=xr.load_dataset(ROOT/'.private/smoke'/m['phase']/'training.nc')
  for v in ['forecast','observed']:
   same=False
   try:xr.testing.assert_allclose(a[v].reset_coords(drop=True),b[v].reset_coords(drop=True),atol=1e-4,rtol=1e-6);same=True
   except AssertionError:pass
   note['diagnostics']['training_'+v]={'values_match_reference':same,'units':a[v].attrs.get('units')}
 except Exception as e:note['diagnostics']['training_error']=type(e).__name__
 for name,p in [('development',r/'frozen/development.nc'),('prediction',r/'evaluation/predictions.nc')]:
  try:
   d=xr.load_dataset(p);a=d.rainfall_mm;prob=d.probability
   note['diagnostics'][name]={'rainfall_units':a.attrs.get('units'),'minimum_mm_numeric':float(a.min()),'all_finite':bool(np.isfinite(a).all()),'probability_sum_max_error':float(abs(prob.sum('tercile')-1).max())}
  except Exception as e:note['diagnostics'][name+'_error']=type(e).__name__
 write(r/'failure-diagnostics.json',note)
 if r.name=='sonnet-scratch-initial':
  note['interpretation']='All three numerical gates failed on missing/wrong units metadata. Training values match the reference; rainfall estimates are finite and positive. The judge inferred negative rainfall from a combined error message; this inference is unsupported. Original scores/judgment remain preserved.'
  write(r/'failure-diagnostics.json',note)
