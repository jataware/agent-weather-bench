// Rasterize the repo-native SVG assets in a browser. No hosted fonts or services.
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.AWB_PLAYWRIGHT_MODULE || 'playwright');

async function exportAssets() {
  const options = {headless:true};
  if (process.env.AWB_CHROME_EXECUTABLE) options.executablePath=process.env.AWB_CHROME_EXECUTABLE;
  const browser=await chromium.launch(options);
  const assets=[
    ['hero',1440,360,1],
    ['social-card',1200,630,1],
    ['benchmark-design',1440,820,2],
    ['agent-task-comparison',1560,770,2],
    ['icon',512,512,1],
    ['symbol',512,512,1],
    ['wordmark',920,160,2],
  ];
  try {
    for(const [name,width,height,scale] of assets) {
      const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:scale});
      const page=await context.newPage();
      await page.goto(pathToFileURL(path.join(__dirname,name+'.svg')).href);
      await page.evaluate(({width,height})=>{
        document.documentElement.style.width=width+'px';
        document.documentElement.style.height=height+'px';
      },{width,height});
      await page.screenshot({path:path.join(__dirname,name+'.png'),omitBackground:true});
      if(name==='agent-task-comparison') {
        await page.pdf({path:path.join(__dirname,name+'.pdf'),width:width+'px',height:height+'px',
          printBackground:true,margin:{top:0,bottom:0,left:0,right:0}});
      }
      await context.close();
    }
  } finally {await browser.close();}
  console.log('Exported 7 PNG assets and the paper figure PDF.');
}

if(require.main===module) exportAssets().catch(error=>{console.error(error);process.exit(1)});
module.exports={exportAssets};
