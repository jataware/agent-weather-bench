"""Synthetic API check only: no benchmark data or reference answers."""
import numpy as np,xarray as xr,json
from africas2s.methods.ensemble_regression import EnsembleRegressionMethod
rng=np.random.default_rng(42)
h=xr.DataArray(rng.uniform(20,100,(12,5,2,2)),dims=['year','member','lat','lon'],coords={'year':range(2000,2012),'member':range(5),'lat':[-1,1],'lon':[36,38]})
o=1.4*h.mean('member')+rng.normal(0,4,(12,2,2))
m=EnsembleRegressionMethod(clip_negative=True).fit(h,o)
m.save('/tmp/model.pkl');loaded=EnsembleRegressionMethod().load('/tmp/model.pkl')
f=h.isel(year=[0]).assign_coords(year=[2020]);before=m.predict_tercile(f,o);after=loaded.predict_tercile(f,o)
xr.testing.assert_identical(before,after)
np.testing.assert_allclose(after.sum('tercile'),1)
assert np.isfinite(after).all() and loaded.is_trained
# Prove inference does not fit again.
loaded.fit=lambda *a,**k: (_ for _ in ()).throw(AssertionError('unexpected refit'))
assert np.isfinite(loaded.predict(f)).all()
assert np.isfinite(loaded.predict_tercile(f,o)).all()
print(json.dumps({'passed':True,'fit_save_load_predict':True,'predict_without_refit':True,'model_state_bytes':__import__('os').path.getsize('/tmp/model.pkl'),'data':'synthetic only'}))
