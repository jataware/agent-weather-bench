"""Build the editable vector identity and an offline README/brand preview."""
import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0,str(ROOT))
from weatherbench.task_tools.render import markdown

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
    social += text(78,567,'MODEL CAPABILITY',15,MINT,500,2)+text(470,567,'COST + TIME',15,MINT,500,2)+text(840,567,'SUBSTRATE',15,MINT,500,2)
    svg('social-card.svg',1200,630,'Benchmark AI models on forecast research','Agent Weather Bench. Measure model capability, cost, and time. Test substrates as an additional comparison.',social)


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
    s += text(760,259,'Solution + trace',25,weight=600,spacing=-.5)
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
    # Reuse begins at the agent/solution lane. Assessments have no path into it.
    s += '<path d="M536 450 V710 H1038 M876 450 V481 H698 V710" fill="none" stroke="#28786b" stroke-width="2.5"/>'
    s += box(734,683,275,51,fill=PAPER,stroke=PAPER,r=0)
    s += text(750,704,'The earlier solution',19,GREEN,500)+text(750,730,'+ the agent\'s state',19,GREEN,500)
    s += arrow('M1007 710 H1066')
    s += box(1076,677,300,91,fill='#e8efe7',r=10)
    s += text(1100,711,'Next instance or task',23,weight=600,spacing=-.4)
    s += text(1100,744,'Same system · compared with a fresh run',16,MUTED)
    svg('benchmark-design.svg',1440,820,'Agent Weather Bench experimental design',
        'Compare models, harnesses and tooling on the same task instances. A task states a product and supplies frozen data and a budget; an agent in a sandbox delivers a solution and a trace; the controller checks it by computation against a private reference, by rerunning the code on changed data, and by a judge that quotes exact text. Every check returns pass, fail or unresolved. Further experiments keep the earlier solution for the next instance, and optimise forecasts for a leaderboard.',s)


def task_comparison():
    """A paper figure: an illustrative paired run, not benchmark results."""
    red,gray = '#a44c3d','#7c8791'
    definitions = '''<defs>
<marker id="flow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M1 1 L9 5 L1 9" fill="none" stroke="#526c6e" stroke-width="1.7"/></marker>
<symbol id="robot" viewBox="0 0 96 96">
<path d="M48 21 V9" stroke="#536976" stroke-width="4"/><circle cx="48" cy="8" r="5" fill="#e5b95e"/>
<rect x="8" y="41" width="10" height="22" rx="4" fill="#8ca3b1"/><rect x="78" y="41" width="10" height="22" rx="4" fill="#8ca3b1"/>
<rect x="17" y="23" width="62" height="61" rx="17" fill="#dce7ec" stroke="#536976" stroke-width="2.5"/>
<rect x="23" y="29" width="50" height="28" rx="10" fill="#f5fafb"/>
<circle cx="34" cy="43" r="6" fill="#19383d"/><circle cx="62" cy="43" r="6" fill="#19383d"/>
<circle cx="32" cy="41" r="1.6" fill="white"/><circle cx="60" cy="41" r="1.6" fill="white"/>
<rect x="30" y="64" width="36" height="11" rx="4" fill="#536976"/><path d="M39 65 V74 M48 65 V74 M57 65 V74" stroke="#e9f1f4" stroke-width="2"/>
</symbol></defs>'''
    s = '<rect width="1560" height="770" fill="white"/>'+definitions
    s += text(48,51,'One task. Two system configurations.',30,weight=600,spacing=-.5)
    s += text(48,83,'Hold the model, inputs, runtime, budget, and judge fixed. Change access to task-specific tools.',19,MUTED)
    s += text(48,130,'(a) Task',20,weight=600)
    s += text(292,130,'Prepare data',20,weight=500)+text(590,130,'Build a forecast',20,weight=500)+text(890,130,'Verify the result',20,weight=500)
    for x in (508,806): s += f'<path d="M{x} 123 H{x+59}" fill="none" stroke="{MUTED}" stroke-width="1.8" marker-end="url(#flow)"/>'
    s += '<path d="M48 157 H1512" stroke="#dce2e5"/>'
    s += text(48,192,'(b) System attempts',20,weight=600)
    s += text(1236,192,'(c) Shared grading',20,weight=600)
    s += box(40,212,1118,177,fill='#f6f8fa',stroke='#f6f8fa',r=12)
    s += box(40,459,1118,179,fill='#eff6f2',stroke='#eff6f2',r=12)
    s += text(61,240,'A  General tools',17,weight=600)
    s += '<use href="#robot" x="98" y="250" width="82" height="82"/>'
    s += text(77,351,'Same AI model',17,weight=500)
    s += text(61,376,'Code + shell',15,MUTED)
    s += text(61,486,'B  With task tools',17,weight=600)
    s += '<use href="#robot" x="98" y="497" width="82" height="82"/>'
    s += text(77,598,'Same AI model',17,weight=500)
    s += text(61,623,'Code + shell + task tools',15,MUTED)

    def status(x,y,state):
        color = GREEN if state=='pass' else red if state=='fail' else gray
        icon = f'<circle cx="{x}" cy="{y}" r="11" fill="white" stroke="{color}" stroke-width="1.8"/>'
        if state=='pass': icon += f'<path d="M{x-5} {y} L{x-1} {y+4} L{x+6} {y-4}" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
        elif state=='fail': icon += f'<path d="M{x-4} {y-4} L{x+4} {y+4} M{x+4} {y-4} L{x-4} {y+4}" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        else: icon += f'<path d="M{x-4} {y} H{x+4}" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        return icon

    def step(x,y,number,title,detail,note,state):
        color = GREEN if state=='pass' else red if state=='fail' else gray
        fill = 'white' if state=='pass' else '#fff6f2' if state=='fail' else '#f2f4f6'
        out = box(x,y,232,125,fill=fill,stroke=color,r=9)
        out += text(x+16,y+32,f'{number}  {title}',20,weight=600)
        out += text(x+16,y+74,detail,17,color,500)
        out += text(x+16,y+103,note,14,MUTED)
        out += status(x+213,y+73,state)
        return out

    # Each illustrated outcome is checked independently. Tool access is not a grade.
    s += step(292,243,1,'Prepare','Valid inputs','Files + coordinates match','pass')
    s += step(590,243,2,'Forecast','Invalid calibration','Reference check fails','fail')
    s += step(888,243,3,'Verify','No valid forecast','Blocked by step 2','fail')
    s += step(292,490,1,'Prepare','Valid inputs','Files + coordinates match','pass')
    s += step(590,490,2,'Forecast','Valid calibration','Saved model + predictions','pass')
    s += step(888,490,3,'Verify','Verified result','Replay + score against data','pass')
    for y in (305,552):
        for x in (524,822):
            dash = ' stroke-dasharray="5 5"' if y==305 and x==822 else ''
            s += f'<path d="M{x+7} {y} H{x+54}" fill="none" stroke="{MUTED}" stroke-width="2"{dash} marker-end="url(#flow)"/>'
        s += f'<path d="M1128 {y} H1207" fill="none" stroke="{MUTED}" stroke-width="2" marker-end="url(#flow)"/>'

    # Thin labelled attachments distinguish available tools from the task steps.
    for x,label in [(292,'Data access'),(590,'Calibration'),(888,'Verification')]:
        s += box(x,421,232,37,fill='#e0eee6',stroke='#abc6b7',r=7)
        s += text(x+16,446,label,16,GREEN,500)
        s += f'<path d="M{x+116} 458 V482" fill="none" stroke="{GREEN}" stroke-width="1.6" stroke-dasharray="3 3" marker-end="url(#flow)"/>'
    s += text(61,446,'Available task tools →',14,GREEN,500)

    s += box(1220,212,292,426,fill='white',stroke='#b7c6ca',r=12)
    s += text(1240,249,'Same checks',23,weight=600)
    s += text(1240,279,'Reference · reruns · judge',16,MUTED)
    s += '<path d="M1240 293 H1492" stroke="#dce2e5"/>'
    s += text(1240,336,'A  Partial',22,red,600)
    s += text(1240,367,'Prepare passed. Forecast failed.',15,MUTED)
    s += text(1240,391,'Verification blocked, so failed.',15,MUTED)
    s += '<path d="M1240 414 H1492" stroke="#dce2e5"/>'
    s += text(1240,461,'Private grading evidence',17,weight=500)
    s += text(1240,488,'Reference outputs + observations',14,MUTED)
    s += text(1240,539,'B  Complete',22,GREEN,600)
    s += text(1240,569,'All required outcomes passed.',15,MUTED)
    s += '<path d="M1240 589 H1492" stroke="#dce2e5"/>'
    s += text(1240,618,'Record tokens, cost, and time.',16,weight=500)
    s += text(49,671,'✓ passed     × failed',15,MUTED)
    s += text(49,716,'Illustrative attempts, not measured benchmark results.',17,weight=600)
    s += text(49,744,'Tool access may change success, cost, or time. Measure its effect with paired runs across models and tasks.',16,MUTED)
    svg('agent-task-comparison.svg',1560,770,'An agent attempts the same three-step task with and without task tools',
        'Two identical emoji-style robot agents represent the same AI model. Both prepare data, build a forecast, and verify it. The general-tools example passes preparation, fails calibration, and leaves verification incomplete. The task-tools example uses data access, calibration, and verification tools and completes all steps. Both are graded with the same private rubric and evidence. The outcomes are illustrative, not measured results.',s)


def readme_html():
    source=(ROOT / 'README.md').read_text()
    images=[]
    def placeholder(match):
        images.append(f'<img src="{html.escape(Path(match[2]).name)}" alt="{html.escape(match[1],quote=True)}" loading="lazy">')
        return 'IMAGEPLACEHOLDER'+str(len(images)-1)
    source=re.sub(r'!\[([^\]]*)\]\(([^)]+)\)',placeholder,source)
    rendered=markdown(source)
    for i,img in enumerate(images): rendered=rendered.replace('<p>IMAGEPLACEHOLDER'+str(i)+'</p>',img)
    def links(match):
        target=html.unescape(match[1])
        if target.startswith(('http:','https:','#','mailto:')): return match[0]
        return 'href="../../../'+html.escape(target,quote=True)+'"'
    rendered=re.sub(r'href="([^"]+)"',links,rendered)
    # Match GitHub's anchor IDs, independently of the preview's heading level.
    def heading(match):
        tag,body=match.groups()
        name=re.sub(r'[^a-z0-9 -]','',html.unescape(re.sub('<[^>]*>','',body)).lower()).replace(' ','-')
        return f'<{tag} id="{name}">{body}</{tag}>'
    return re.sub(r'<(h[1-6])>(.*?)</\1>',heading,rendered)


def preview():
    css=(HERE / 'preview.css').read_text()
    page=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Agent Weather Bench · README and identity</title><link rel="icon" href="icon.svg"><style>{css}</style></head>
<body><header class="masthead"><a href="#" class="identity"><img src="symbol.svg" alt="" width="36" height="36"><span>Agent Weather Bench</span></a><nav aria-label="Preview sections"><a href="#readme">README</a><a href="#task-figure">Figure</a><a href="#identity">Identity</a><a href="#share">Share assets</a></nav></header>
<main><section class="intro"><p class="eyebrow">PUBLIC IDENTITY / WORKING DRAFT</p><h1>Compare AI models<br>on forecast research.</h1><p>Measure completion, cost, and time. Then test what skills, code, and prior work add.</p></section>
<section id="readme" class="readme-section"><div class="section-label"><span>01 / README</span><a href="../../../README.md">View Markdown source ↗</a></div><article class="readme">{readme_html()}</article></section>
<section id="task-figure"><div class="section-label"><span>02 / TASK, SYSTEMS, AND GRADING</span><a href="agent-task-comparison.svg">Open full-size figure ↗</a></div><img src="agent-task-comparison.svg" alt="A robot agent attempts a three-step forecasting task with and without task-specific tools. Both attempts use the same grader."><div class="downloads"><a href="agent-task-comparison.svg" download>Editable SVG</a><a href="agent-task-comparison.png" download>PNG</a><a href="agent-task-comparison.pdf" download>Vector PDF</a></div></section>
<section id="identity"><div class="section-label"><span>03 / IDENTITY</span><span>Agent Weather Bench</span></div><div class="brand-grid"><div class="brand-panel light"><img src="wordmark.svg" alt="Agent Weather Bench wordmark"><p>A descriptive name makes the subject clear. The subtitle states the benchmark's scope.</p></div><div class="brand-panel dark"><img src="symbol-inverse.svg" alt="Inverse contour symbol"><p>Weather contours.<br>One point for a checked result.</p></div></div>
<div class="swatches"><div style="--swatch:{INK}"><span>Ink</span><code>{INK}</code></div><div style="--swatch:{PAPER}"><span>Paper</span><code>{PAPER}</code></div><div style="--swatch:{GREEN}"><span>Field</span><code>{GREEN}</code></div><div style="--swatch:{MINT}"><span>Contour</span><code>{MINT}</code></div><div style="--swatch:{GOLD}"><span>Measure</span><code>{GOLD}</code></div></div>
<div class="principles"><div><h3>Name</h3><p>Agent Weather Bench is the selected working name. Use all three words. Use AWB only after introducing the name.</p></div><div><h3>Voice</h3><p>Use short sentences, active verbs, and stable terms. Define domain words. Use simplified technical English as a guide, without claiming formal compliance.</p></div><div><h3>Graphics</h3><p>Use vectors for methods and diagrams. Keep data, execution, and private assessment paths clear. Show measured curves only when results exist.</p></div></div>
</section><section id="share"><div class="section-label"><span>04 / SHARE ASSETS</span><span>Editable SVG + PNG exports</span></div><img class="share-card" src="social-card.svg" alt="Agent Weather Bench share card: Benchmark AI models on forecast research."><div class="downloads"><a href="social-card.png" download>Share card · PNG</a><a href="social-card.svg" download>Share card · SVG</a><a href="benchmark-design.png" download>Diagram · PNG</a><a href="benchmark-design.svg" download>Diagram · SVG</a><a href="icon.png" download>Icon · PNG</a><a href="symbol.svg" download>Symbol · SVG</a><a href="wordmark.svg" download>Wordmark · SVG</a><a href="brand-guide.md">Brand guide ↗</a></div></section>
<footer>Agent Weather Bench · A benchmark for AI forecast research.<br>This preview opens offline. The README and vector sources remain editable.</footer></main></body></html>'''
    (HERE / 'index.html').write_text(page)


if __name__ == '__main__':
    vectors(); diagram(); task_comparison(); preview()
    print('Built 9 SVG assets and the offline README/brand preview.')
