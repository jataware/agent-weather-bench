"""Synthetic public API demonstration; no benchmark inputs or answers."""
import numpy as np
import xarray as xr
from weather_skills_core.units import deaccumulate_along_step


def main():
    data=xr.Dataset({'tp':(('step','latitude','longitude'),np.asarray([0.,.002,.008,.014])[:,None,None],{'units':'m'})},
                    coords={'step':np.asarray([0,12,36,60],dtype='timedelta64[h]'),
                            'time':np.datetime64('2001-01-01'),'latitude':[1.],'longitude':[37.]})
    result=deaccumulate_along_step(data,names=['tp'])
    actual=result.tp.values.ravel()
    np.testing.assert_allclose(actual,[4.,6.,6.],rtol=0,atol=2e-12)
    assert result.tp.attrs['units']=='mm day-1'
    print('Synthetic rates (mm/day):',actual.tolist())
    print('Ending steps:',result.step.values.tolist())
    negative=data.copy(deep=True);negative['tp'].values[:,0,0]=[0,.002,.001,.005]
    clipped=deaccumulate_along_step(negative,names=['tp'])
    np.testing.assert_allclose(clipped.tp.values.ravel(),[4.,0.,4.],rtol=0,atol=2e-12)
    print('Synthetic negative-increment clipping:',clipped.tp.values.ravel().tolist())


if __name__=='__main__':main()
