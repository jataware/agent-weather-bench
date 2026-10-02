"""Export the plain HTML slide preview with local headless Chrome."""
import subprocess,time
from pathlib import Path
from pilot.common import ROOT
import sys
stem=sys.argv[1] if len(sys.argv)>1 else 'three-smoke-slides'
chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
url=(ROOT/'slides'/f'{stem}.html').as_uri()
args=[chrome,'--headless','--disable-gpu','--no-sandbox','--no-first-run','--no-default-browser-check','--user-data-dir='+str(ROOT/'.private/chrome-slide-preview'),'--no-pdf-header-footer','--print-to-pdf='+str(ROOT/'slides'/f'{stem}.pdf'),url]
p=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 p.wait(timeout=25)
except subprocess.TimeoutExpired:
 p.terminate()
 try:p.wait(timeout=3)
 except subprocess.TimeoutExpired:p.kill()
print('PDF exists:',(ROOT/'slides'/f'{stem}.pdf').exists())
