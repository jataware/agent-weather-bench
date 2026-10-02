"""Append three measured-smoke slides in the check-in deck's existing plain style."""
import json,shutil
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
from pilot.common import ROOT,read

base=ROOT/'slides/checkin-original.pptx'
if not base.exists():shutil.copy2(ROOT/'2026-10-01-accord-checkin.pptx',base)
prs=Presentation(base)
summary=read(ROOT/'results/smoke-summary.json') if (ROOT/'results/smoke-summary.json').exists() else {'runs':{}}
data=summary['runs']

def get(key):return data.get(key,{})
def fmt(key,field,default='—'):
 value=get(key).get(field)
 if value is None:return default
 if field=='usd':return f'${value:.2f}'+('+' if get(key).get('usage_incomplete') else '')
 if field=='seconds':return f'{value/60:.1f} min'
 if field=='tokens':return f'{value:,}'
 if field=='rps':return f'{value:.3f}'
 return str(value)

def text(slide,x,y,w,h,value,size=18,bold=False,color='111111'):
 shape=slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));tf=shape.text_frame
 tf.margin_left=tf.margin_right=0;tf.word_wrap=True
 for i,line in enumerate(value.split('\n')):
  p=tf.paragraphs[0] if i==0 else tf.add_paragraph();p.text=line
  p.font.name='Calibri';p.font.size=Pt(size);p.font.bold=bold;p.font.color.rgb=RGBColor.from_string(color)
  p.space_after=Pt(12)
 return shape

def slide(title):
 s=prs.slides.add_slide(prs.slide_layouts[0])
 # The supplied layout is empty; explicitly retain its plain white background.
 s.background.fill.solid();s.background.fill.fore_color.rgb=RGBColor(255,255,255)
 text(s,.6,.45,12.1,.8,title,30,True)
 text(s,.6,7.0,12.1,.3,f'ACCORD weather pilot · development smoke · 1 Oct 2026 · {len(prs.slides)}',10,color='6B6B6B')
 return s

def table(s,rows,y=2.2,widths=None):
 widths=widths or [3.0]+[(12.1-3)/(len(rows[0])-1)]*(len(rows[0])-1)
 t=s.shapes.add_table(len(rows),len(rows[0]),Inches(.6),Inches(y),Inches(12.1),Inches(.58*len(rows))).table
 for j,w in enumerate(widths):t.columns[j].width=Inches(w)
 for i,row in enumerate(rows):
  for j,value in enumerate(row):
   c=t.cell(i,j);c.text=str(value);c.fill.solid();c.fill.fore_color.rgb=RGBColor.from_string('EEEEEE' if i==0 else 'FFFFFF')
   c.margin_left=Inches(.1);c.margin_top=Inches(.1)
   for p in c.text_frame.paragraphs:
    p.font.name='Calibri';p.font.size=Pt(16);p.font.bold=(i==0);p.font.color.rgb=RGBColor.from_string('111111')
 return t

# Keep the prior experiment, but make its chronology explicit next to the new pilot.
for i in range(9,15):
 s=prs.slides[i]
 for shape in s.shapes:
  if shape.has_text_frame:
   for p in shape.text_frame.paragraphs:
    for r in p.runs:
     r.text=r.text.replace('Current experiment:','Earlier experiment:').replace('Current task:','Earlier task:').replace('Next: test the libraries','Earlier proposal: test the libraries')

s=slide('Can a coding agent build a seasonal forecast workflow?')
text(s,.6,1.5,12.1,1.05,'September-issued OND rainfall in a Kenyan study box.\nAggregate monthly inputs, fit a calibration, save the fitted model, and produce a new forecast.',18)
rows=[['Scratch model','Checks passed','Tokens','Cost','Time']]
for key,label in [('fable-scratch-initial','Fable 5.1'),('haiku-scratch-initial','Haiku 4.5')]:
 rows.append([label,fmt(key,'check_count'),fmt(key,'tokens'),fmt(key,'usd'),fmt(key,'seconds')])
table(s,rows,2.8)
weak=get('haiku-scratch-initial'); strong=get('fable-scratch-initial')
capability=summary.get('capability_finding','Model capability comparison is still running; no capability threshold has been established.')
text(s,.6,4.85,12.1,1.0,capability,18)
text(s,.6,6.05,12.1,.75,'Same inputs and attempt limits. One attempt per condition: an illustration, not a general model ranking.\nMonthly data was supplied; live data discovery and retrieval were not tested.',13,color='6B6B6B')
s.notes_slide.notes_text_frame.text='Source: results/smoke-summary.json and runs/smoke-v3. Models and all raw traces are recorded. Do not infer a universal capability threshold from one small case.'

s=slide('Do skills and domain libraries reduce the work?')
text(s,.6,1.5,12.1,.7,'Same Fable 5.1 model, task, normalized inputs, resources and limits. Only the available domain tools differ.',18)
rows=[['Arm','Checks','Tokens','Cost','Time','Test RPS']]
for arm,label in [('scratch','Python only'),('rhiza','Python + Rhiza'),('accord','Python + ACCORD')]:
 key='fable-'+arm+'-initial';rows.append([label,fmt(key,'check_count'),fmt(key,'tokens'),fmt(key,'usd'),fmt(key,'seconds'),fmt(key,'rps')])
table(s,rows,2.55,[2.7,1.4,2,1.4,1.7,2.9])
text(s,.6,5.15,12.1,1.0,summary.get('tools_finding','Comparison pending. Toolkit availability and actual use are recorded separately.'),18)
text(s,.6,6.2,12.1,.55,'RPS is lower-is-better; two previously inspected development years, not untouched scientific validation.\nNumerical checks, offline replay and an evidence-citing LLM judge assess the outputs.',12,color='6B6B6B')
s.notes_slide.notes_text_frame.text='No weighted leaderboard. Initial infrastructure-aborted attempts are excluded and preserved separately. Agent cost excludes judge/setup cost. Check count includes artifacts, provenance, data aggregation, valid probabilities and reproduction.'

s=slide('What survives into the next forecast?')
text(s,.6,1.5,12.1,.7,'Fresh conversation, same arm’s saved code, fitted model, data and handoff notes. Apply to a different forecast batch.',18)
rows=[['Arm','Saved state','Follow-up checks','Initial → follow-up cost','Follow-up time']]
for arm,label in [('scratch','Python only'),('rhiza','Python + Rhiza'),('accord','Python + ACCORD')]:
 key='fable-'+arm+'-followup';initial='fable-'+arm+'-initial'
 saved=get(initial).get('model_files',[])
 rows.append([label,', '.join(saved) or 'code only',fmt(key,'check_count'),fmt(initial,'usd')+' → '+fmt(key,'usd'),fmt(key,'seconds')])
table(s,rows,2.55,[2.3,2.1,2.2,3.5,2.0])
text(s,.6,5.15,12.1,1.0,summary.get('reuse_finding','Follow-up comparison pending. All arms are allowed to retain and reuse their work.'),18)
text(s,.6,6.2,12.1,.6,'All saved code, models, notes, figures and usage are retained. + marks unrecorded usage from a timed-out request.\nNo fresh-workspace controls; recovery from an incomplete initial attempt is not reuse of a working forecast.',12,color='6B6B6B')
s.notes_slide.notes_text_frame.text='Saved state refers to the initial attempt. A follow-up after an incomplete initial attempt measures recovery, not reuse of a working forecast. Direct saved-predictor timing is in results/direct-reuse-timing.json and includes container startup/cleanup. It is distinct from conversational follow-up cost. Do not imply that only ACCORD can save code or that two verification years establish probabilistic calibration.'

out=ROOT/'2026-10-01-accord-checkin.pptx';prs.save(out)
# A separate three-slide extract is convenient for review, while the full deck keeps its original 15 slides.
for item in list(prs.slides._sldIdLst)[:15]:
 prs.part.drop_rel(item.rId);prs.slides._sldIdLst.remove(item)
prs.save(ROOT/'slides/three-smoke-slides.pptx')
print('Updated copied check-in deck (18 slides) and three-slide extract.')
