"""Kenya locator for the existing seasonal task; no simulated forecast values."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Rectangle
from pilot.common import ROOT,write,digest
boundary=ROOT/'slides/assets/kenya-boundary.geojson'
g=json.loads(boundary.read_text())['features'][0]['geometry']
rings=g['coordinates'] if g['type']=='Polygon' else [r for p in g['coordinates'] for r in p]
fig,ax=plt.subplots(figsize=(3.0,3.2),layout='constrained')
for ring in rings:ax.add_patch(Polygon(ring,closed=True,facecolor='#f3f3f3',edgecolor='#777777',linewidth=1))
ax.add_patch(Rectangle((36,-3),3,4,facecolor='#8a1c1c',edgecolor='#8a1c1c',alpha=.18,linewidth=1.3))
for lon in [36,37,38,39]:ax.plot([lon,lon],[-3,1],color='#8a1c1c',lw=.7)
for lat in [-3,-2,-1,0,1]:ax.plot([36,39],[lat,lat],color='#8a1c1c',lw=.7)
ax.text(37.5,3.1,'KENYA',ha='center',fontsize=13,color='#333333')
ax.text(37.5,-4.9,'Same 12-cell study area',ha='center',fontsize=10,color='#8a1c1c')
ax.set_xlim(33.5,42.5);ax.set_ylim(-5.6,5.5);ax.set_aspect('equal');ax.axis('off')
for ext in ['png','svg']:fig.savefig(ROOT/f'slides/assets/kenya-study-area.{ext}',dpi=200,facecolor='white')
plt.close(fig)
write(ROOT/'slides/assets/kenya-study-area.json',{'boundary_source':'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson','boundary_sha256':digest(boundary),'study_bounds':{'west':36,'east':39,'south':-3,'north':1},'cells':12,'description':'Locator only. Both initial and follow-up tasks use this same study box; the forecast years change. Natural Earth 1:110m generalized country boundary.'})
