"""Plot an existing forecast artifact, without modifying or rerunning the submission."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json
from matplotlib.patches import Polygon,Rectangle
import numpy as np
import xarray as xr
from pilot.common import ROOT, write, digest
source=ROOT/'runs/revision-v1/fable-accord-initial/evaluation/predictions.nc'
d=xr.load_dataset(source)
a=d.probability.sel(year=2005,tercile='above').transpose('lat','lon')
fig,(locator,ax)=plt.subplots(1,2,figsize=(7.0,4.8),gridspec_kw={'width_ratios':[1,1.65]},layout='constrained')
boundary=ROOT/'slides/assets/kenya-boundary.geojson'
g=json.loads(boundary.read_text())['features'][0]['geometry']
rings=g['coordinates'] if g['type']=='Polygon' else [r for poly in g['coordinates'] for r in poly]
for ring in rings:locator.add_patch(Polygon(ring,closed=True,facecolor='#f3f3f3',edgecolor='#777777',linewidth=1))
locator.add_patch(Rectangle((36,-3),3,4,facecolor='#8a1c1c',edgecolor='#8a1c1c',alpha=.22,linewidth=1.2))
locator.text(37.5,3.1,'KENYA',ha='center',fontsize=13)
locator.text(37.5,-5.2,'Study box →',ha='center',fontsize=12,color='#8a1c1c')
locator.set_xlim(33,43);locator.set_ylim(-6,5.5);locator.set_aspect('equal');locator.axis('off')
plot=ax.pcolormesh(np.arange(36,40),np.arange(-3,2),a.values,vmin=0,vmax=1,cmap='YlGnBu',edgecolors='white',linewidth=.8)
for lat in a.lat.values:
 for lon in a.lon.values:
  v=float(a.sel(lat=lat,lon=lon))
  ax.text(lon,lat,f'{v:.0%}',ha='center',va='center',fontsize=12,color='white' if v>.55 else '#111111')
ax.set_aspect('equal');ax.set_xticks([36,37,38,39],['36°E','37°E','38°E','39°E'])
ax.set_yticks([-3,-2,-1,0,1],['3°S','2°S','1°S','0°','1°N'])
ax.tick_params(length=0,labelsize=10,pad=6)
for spine in ax.spines.values():spine.set_color('#bbbbbb')
ax.set_title('Above-normal rainfall probability\nOctober–December 2005',fontsize=13,loc='left',pad=14)
c=fig.colorbar(plot,ax=ax,shrink=.8,pad=.08,ticks=[0,1/3,2/3,1]);c.ax.set_yticklabels(['0%','33%','67%','100%']);c.outline.set_visible(False)
c.set_label('Probability',fontsize=11)
fig.savefig(ROOT/'slides/assets/tercile-example.png',dpi=200,facecolor='white')
fig.savefig(ROOT/'slides/assets/tercile-example.svg',facecolor='white')
plt.close(fig)
write(ROOT/'slides/assets/tercile-example.json',{'source':str(source.relative_to(ROOT)),'source_sha256':digest(source),'boundary_source':'Natural Earth 1:110m; slides/assets/kenya-study-area.json','boundary_sha256':digest(boundary),'run':'fable-accord-initial','year':2005,'tercile':'above','training_years':'1993–2004','description':'Historical example from an evaluated frozen predictor. A 12-cell study box, not a national forecast. Above-normal means above the observed training upper-tercile threshold. Each grid cell shows the probability of that category; remaining probability is below or near normal. No inference about forecast quality from this image alone.'})
