"""Initial bounded anonymous source extraction; run explicitly with network approval.

Downloads selected regional HTTP ranges, never whole input dataframes or tokens.
Frozen subsets thereafter prepare offline.
"""
from weatherbench.task_tools.subseasonal.acquire import open_public
from pathlib import Path
import h5py,numpy as np,xarray as xr,json,hashlib,urllib.request,concurrent.futures

def main():
    root=Path(__file__).resolve().parents[3]/'var/private/tasks/subseasonal-optimization';c=root/'controller'; c.mkdir(parents=True,exist_ok=True)
    if (c/'source-subset.nc').exists():raise ValueError('Source subset already frozen; do not overwrite')
    audit=[]
    rf=open_public('iri-cfsv2-precip-all-us1_5-ensembled.h5',max_bytes=150000000);rf.block_size=1048576
    with h5py.File(rf,'r') as f:
     dates=f['data/block0_values'][:,0].astype('datetime64[ns]');n=376
     print('dates',dates[0],dates[-1],len(dates),flush=True)
     locations=f['data/block2_values'][:n];print('geo',locations.shape,flush=True)
     chosen=np.flatnonzero((locations[:,0]>=33)&(locations[:,0]<=36)&(locations[:,1]>=246)&(locations[:,1]<=249));print('chosen',locations[chosen],flush=True)
     names=[x.decode() for x in f['data/block1_items'][:]];col=names.index('iri_cfsv2_precip-14.5d');print('column',col,flush=True)
     offset_val=f['data/block1_values'].id.get_offset();offset_geo=f['data/block2_values'].id.get_offset()
     first=np.flatnonzero(np.r_[True,dates[1:]!=dates[:-1]])
     weekly=first[(dates[first]>=np.datetime64('1999-01-01'))&(dates[first]<np.datetime64('2022-01-01'))&((dates[first].astype('datetime64[D]').astype(int)-3)%7==0)]
     starts=[int(i) for i in weekly];stamp=dates[weekly]; coords=locations[chosen]
    rf.block_size=4096;rf.cache={}
    # Preload only blocks covering each selected location row, both values and coords.
    requests=set()
    for start in starts:
     for j in chosen:
      for offset,stride in [(offset_val,120),(offset_geo,16)]:
       lo=offset+(start+int(j))*stride;hi=lo+stride-1
       requests.update(range(lo//4096,hi//4096+1))
    if rf.bytes_read+len(requests)*4096>rf.maximum:raise ValueError('Planned ranges exceed source download cap')
    print('preload',len(requests),'blocks',flush=True)
    def load(index):
     start=index*4096;stop=min(rf.size,start+4096)-1
     req=urllib.request.Request(rf.url,headers={'Range':f'bytes={start}-{stop}','If-Match':rf.etag})
     with urllib.request.urlopen(req,timeout=60) as r:
      if r.status!=206:raise ValueError('Range failure')
      body=r.read()
     if len(body)!=stop-start+1:raise ValueError('Wrong range length')
     return index,body
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
     for index,body in pool.map(load,sorted(requests)):
      rf.cache[index]=body;rf.bytes_read+=len(body);rf.requests+=1
    raw=[]
    for start,t in zip(starts,stamp):
     if not np.all(dates[start+chosen]==t):raise ValueError('Rowcalendar mismatch')
     values=[]
     for j in chosen:
      rf.seek(offset_geo+(start+int(j))*16);geo=np.frombuffer(rf.read(16),dtype='<f8');np.testing.assert_array_equal(geo,locations[j])
      rf.seek(offset_val+(start+int(j))*120);row=np.frombuffer(rf.read(120),dtype='<f4');values.append(row[col])
     raw.append(values)
    raw=np.asarray(raw)
    audit.append({'source':'iri-cfsv2-precip-all-us1_5-ensembled.h5','content_length':rf.size,'etag':rf.etag,'downloaded_bytes':rf.bytes_read,'requests':rf.requests,'selected_rows':len(raw)*len(chosen)})
    print('forecast extracted',raw.shape,rf.bytes_read,flush=True)
    rf=open_public('gt-us_precip_1.5x1.5-14d.h5');rf.block_size=1048576
    with h5py.File(rf,'r') as f:
     lat=f['data/axis1_level0'][:];lon=f['data/axis1_level1'][:];times=f['data/axis1_level2'][:].astype('datetime64[ns]');a=f['data/axis1_label0'][:];b=f['data/axis1_label1'][:];t=f['data/axis1_label2'][:]
     # Public obs coordinate labels read; values only chosen region spanning required period.
     offset=f['data/block0_values'].id.get_offset()
     obs=[]
     for latitude,longitude in coords:
      ix=np.flatnonzero((a==np.flatnonzero(lat==latitude)[0])&(b==np.flatnonzero(lon==longitude)[0]))
      lookup={times[t[i]]:int(i) for i in ix}
      rows=np.array([lookup[np.datetime64(x,'ns')+np.timedelta64(14,'D')] for x in stamp]);assert np.all(np.diff(rows)>0)
      rf.seek(offset+int(rows[0])*4);vals=np.frombuffer(rf.read((int(rows[-1])-int(rows[0])+1)*4),dtype='<f4');obs.append(vals[rows-rows[0]])
    obs=np.asarray(obs).T
    audit.append({'source':'gt-us_precip_1.5x1.5-14d.h5','content_length':rf.size,'etag':rf.etag,'downloaded_bytes':rf.bytes_read,'requests':rf.requests,'selected_rows':obs.size})
    if not np.isfinite(raw).all() or not np.isfinite(obs).all():
     print('nonfinite forecast/obs',np.sum(~np.isfinite(raw)),np.sum(~np.isfinite(obs)),flush=True)
    # Shared complete-support issue selection happens without inspecting skill.
    valid=np.isfinite(raw).all(axis=1)&np.isfinite(obs).all(axis=1)
    raw,obs,stamp=raw[valid],obs[valid],stamp[valid]
    ds=xr.Dataset({'raw_cfsv2':(('issue_time','location'),raw), 'precipitation':(('issue_time','location'),obs)},coords={'issue_time':stamp,'location':np.arange(len(coords)),'latitude':('location',coords[:,0]),'longitude':('location',coords[:,1]),'target_start':('issue_time',stamp+np.timedelta64(14,'D'))})
    for v in ['raw_cfsv2','precipitation']:ds[v].attrs['units']='mm'
    ds.attrs={'target':'14-day precipitation total beginning issue_time +14 days','source_forecast_column':'iri_cfsv2_precip-14.5d','retrospective_source_vintage':'2026-10-05','not_pristine_holdout':'Historical public outcomes, now withheld in controller only'}
    ds.to_netcdf(c/'source-subset.nc')
    (c/'acquisition-audit.json').write_text(json.dumps({'sources':audit,'total_downloaded_bytes':sum(x['downloaded_bytes'] for x in audit),'complete_issues':len(stamp),'dropped_nonfinite_issues':int(sum(~valid))},indent=2)+'\n')
    print('DONE',ds.sizes,sum(x['downloaded_bytes'] for x in audit),flush=True)

if __name__=="__main__":main()
