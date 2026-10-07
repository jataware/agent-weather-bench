"""Build the editable vector identity and the benchmark diagram."""
import html
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

INK = '#19383d'
PAPER = '#f6f4ed'
GREEN = '#28786b'
MINT = '#92d1bf'
GOLD = '#e5b95e'
MUTED = '#526c6e'
LINE = '#cbd7d0'
FONT = 'Arial, Helvetica, sans-serif'


def svg(name,width,height,title,description,body):
    content = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">
<title id="title">{html.escape(title)}</title><desc id="description">{html.escape(description)}</desc>
{body}
</svg>\n'''
    (HERE / name).write_text(content)


def text(x,y,value,size=22,color=INK,weight=400,spacing=None):
    tracking = f' letter-spacing="{spacing}"' if spacing is not None else ''
    return f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" fill="{color}"{tracking}>{html.escape(value)}</text>'


def mark(x=0,y=0,scale=1,color=GREEN,accent=GOLD):
    return f'''<g transform="translate({x} {y}) scale({scale})" fill="none" stroke="{color}" stroke-width="7" stroke-linecap="round">
<path d="M16 56 C36 56 36 24 60 24 S86 56 112 56"/>
<path d="M16 78 C36 78 36 46 60 46 S86 78 112 78"/>
<path d="M16 100 C36 100 36 68 60 68 S86 100 112 100"/>
<circle cx="60" cy="24" r="7" fill="{accent}" stroke="none"/>
</g>'''


def contours(x,y,color,scale=1):
    paths=[]
    for i in range(9):
        o=i*24
        paths.append(f'<path d="M{-o} 310 C{-o} {150-o} {140-o} {-o} 300 {-o} S{600+o} {100-o} {620+o} 280 S{430+o} {460+o} 260 {460+o}"/>')
    return f'<g transform="translate({x} {y}) scale({scale})" fill="none" stroke="{color}" stroke-width="1.2">'+''.join(paths)+'</g>'


def box(x,y,w,h,fill=PAPER,stroke=LINE,r=12):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}"/>'


def arrow(path,color=GREEN,dashed=False):
    return f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.5"'+(' stroke-dasharray="6 6"' if dashed else '')+' marker-end="url(#arrow)"/>'


def vectors():
    description = 'Three weather contours represent forecast research. A gold point marks a checked result.'
    svg('symbol.svg',128,128,'Agent Weather Bench symbol',description,mark())
    svg('symbol-inverse.svg',128,128,'Agent Weather Bench inverse symbol',description,mark(color=MINT))
    svg('symbol-mono.svg',128,128,'Agent Weather Bench monochrome symbol',description,mark(color=INK,accent=INK))
    svg('icon.svg',128,128,'Agent Weather Bench icon',description,
        f'<rect width="128" height="128" rx="28" fill="{INK}"/>'+mark(color=MINT))
    svg('wordmark.svg',920,160,'Agent Weather Bench','A contour symbol beside the project name.',
        mark(8,12)+text(158,82,'Agent Weather Bench',54,weight=600,spacing=-1.5)+text(160,118,'A benchmark for AI forecast research',22,MUTED))
    hero = f'<rect width="1440" height="360" fill="{INK}"/>'
    hero += contours(1150,140,'#325456',.85)
    hero += text(60,58,'WEATHER + CLIMATE RESEARCH',15,MINT,500,2.2)
    hero += mark(54,95,1.25,MINT)
    hero += text(247,187,'Agent Weather Bench',72,PAPER,600,-2.7)
    hero += text(251,238,'A benchmark for AI forecast research',29,'#c5d8d1')
    hero += text(60,316,'MODELS   /   TASKS   /   VERIFIED RESULTS',13,MINT,500,2.1)
    svg('hero.svg',1440,360,'Agent Weather Bench','A benchmark for AI forecast research. Compare model capability, cost, and time. Test added support separately.',hero)
    social = f'<rect width="1200" height="630" fill="{INK}"/>'
    social += contours(1010,290,'#325456',.9)+mark(58,55,1.25,MINT)
    social += text(240,124,'Agent Weather Bench',49,PAPER,600,-1.7)
    social += text(74,300,'Benchmark AI models',67,PAPER,600,-2.0)
    social += text(74,380,'on forecast research.',67,PAPER,600,-2.0)
    social += text(78,462,'Scientific tasks. Checked results.',29,'#c5d8d1')
    social += '<path d="M78 525 H1122" stroke="#476364"/>'
    social += text(78,567,'MODEL CAPABILITY',15,MINT,500,2)+text(470,567,'COST + TIME',15,MINT,500,2)+text(840,567,'TOOLING',15,MINT,500,2)
    svg('social-card.svg',1200,630,'Benchmark AI models on forecast research','Agent Weather Bench. Measure model capability, cost, and time. Test tooling as an additional comparison.',social)


def diagram():
    s = f'<rect width="1440" height="820" rx="16" fill="{PAPER}"/>'
    s += '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M1 1 L9 5 L1 9" fill="none" stroke="#28786b" stroke-width="1.5"/></marker></defs>'
    s += text(56,57,'THE BENCHMARK',15,GREEN,600,2)
    s += text(56,111,'Same tasks. Different systems.',43,INK,600,-1)
    s += text(57,149,'Compare models, harnesses and tooling on the same task instances, with the same checks each time.',22,MUTED)
    xvals=[56,396,736,1076]
    labels=['01 / DEFINE','02 / EXECUTE','03 / CAPTURE','04 / ASSESS']
    for x,label in zip(xvals,labels): s += text(x,197,label,14,GREEN,600,1.4)
    for x in xvals: s += box(x,212,300 if x==1076 else 280,238,fill='#ffffff' if x!=396 else '#e8efe7')
    s += text(80,259,'Task + tooling',25,weight=600,spacing=-.5)
    for y,label in zip([301,332,363],['A product, not a method','Frozen data · a budget','Tooling in or out']): s += text(80,y,label,20,MUTED)
    s += '<path d="M80 387 H312" stroke="#cbd7d0"/>'+text(80,421,'Region and window are parameters',17,GREEN)
    s += text(420,259,'Agent in a sandbox',25,weight=600,spacing=-.6)
    for y,label in zip([301,332,363],['A model, driven by a harness','No network · fixed budget','Any method, any code']): s += text(420,y,label,18,MUTED)
    s += '<path d="M420 387 H652" stroke="#cbd7d0"/>'+text(420,421,'Skills · libraries · earlier work',17,GREEN)
    s += text(760,259,'Submission + trace',25,weight=600,spacing=-.5)
    for y,label in zip([301,332,363],['Labelled arrays + answer','Code that regenerates them','Report · every command']): s += text(760,y,label,20,MUTED)
    s += '<path d="M760 387 H992" stroke="#cbd7d0"/>'+text(760,421,'Hashes, cost and time kept by the controller',15,GREEN)
    s += text(1100,259,'Controller checks',25,weight=600,spacing=-.5)
    for y,label in zip([301,332,363],['Compute against a reference','Rerun the code on changed data','Judge on exact quotations']): s += text(1100,y,label,18,MUTED)
    s += '<path d="M1100 387 H1352" stroke="#cbd7d0"/>'+text(1100,421,'Pass · fail · unresolved, per check',17,GREEN)
    for a,b in [(336,396),(676,736),(1016,1076)]: s += arrow(f'M{a+7} 327 H{b-9}')
    s += box(736,500,640,116,fill='#edece4',r=10)
    s += text(760,531,'CONTROLLER ONLY',13,GREEN,600,1.4)
    s += text(760,562,'Private reference under every reading + withheld observations',21,weight=500)
    s += text(760,592,'A known wrong reading is named as a pitfall. Skill is scored for forecasts.',16,MUTED)
    s += arrow('M1226 500 V459',dashed=True)
    s += text(56,520,'PRIMARY COMPARISON',14,GREEN,600,1.5)
    s += text(56,557,'Model · harness · tooling',23,weight=500)
    s += text(56,591,'Pass rate, cost and time per task',23,weight=500)
    s += '<path d="M56 647 H1376" stroke="#cbd7d0"/>'
    s += text(56,693,'ADDITIONAL EXPERIMENTS',14,GREEN,600,1.5)
    s += text(56,731,'Episodes: keep the earlier work.',23,weight=500)
    s += text(56,764,'Leaderboard: optimise the forecast within a budget.',19,MUTED)
    # Reuse begins at the agent/submission lane. Assessments have no path into it.
    s += '<path d="M536 450 V710 H1038 M876 450 V481 H698 V710" fill="none" stroke="#28786b" stroke-width="2.5"/>'
    s += box(734,683,275,51,fill=PAPER,stroke=PAPER,r=0)
    s += text(750,704,'The earlier submission',19,GREEN,500)+text(750,730,'+ the agent\'s state',19,GREEN,500)
    s += arrow('M1007 710 H1066')
    s += box(1076,677,300,91,fill='#e8efe7',r=10)
    s += text(1100,711,'Next instance or task',23,weight=600,spacing=-.4)
    s += text(1100,744,'Same system · compared with a fresh run',16,MUTED)
    svg('benchmark-design.svg',1440,820,'Agent Weather Bench experimental design',
        'Compare models, harnesses and tooling on the same task instances. A task states a product and supplies frozen data and a budget; an agent in a sandbox hands back a submission and a trace; the controller checks it by computation against a private reference, by rerunning the code on changed data, and by a judge that quotes exact text. Every check returns pass, fail or unresolved. Further experiments keep the earlier submission for the next instance, and optimise forecasts for a leaderboard.',s)


if __name__ == '__main__':
    vectors(); diagram()
    print('Built the SVG identity assets and the benchmark diagram.')
