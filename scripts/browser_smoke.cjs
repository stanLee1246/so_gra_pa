// 可选浏览器验证，需要 Playwright 与 Chromium；应用运行无需 Node。
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const base = process.env.APP_BASE_URL || 'http://127.0.0.1:8000';
(async () => {
  const browser = await chromium.launch({headless:true, ...(process.env.CHROMIUM_PATH ? {executablePath:process.env.CHROMIUM_PATH} : {}), args:['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors = [], external = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => {if(!r.url().startsWith(base)) external.push(r.url());});
    await page.goto(base);
    const loaded = () => page.waitForFunction(() => document.querySelector('#export').getAttribute('aria-disabled') === 'false');
    await loaded();
    assert.equal(await page.locator('#total').innerText(), '12,010');
    assert.equal(await page.evaluate(() => Object.keys(charts).length), 7);
    await page.selectOption('#year','2024');
    await loaded();
    assert.equal(await page.locator('#total').innerText(), '4,000');
    const initialRow = await page.locator('#rows tr').first().innerText();
    await page.click('#next');
    await page.waitForFunction(() => document.querySelector('#pageInfo').textContent.includes('第 2 页'));
    assert.notEqual(await page.locator('#rows tr').first().innerText(), initialRow);
    const downloadPromise = page.waitForEvent('download');
    await page.click('#export');
    const download = await downloadPromise;
    assert.equal(download.suggestedFilename(),'simulated_complaints.csv');
    const stream = await download.createReadStream();
    let csv=''; for await (const chunk of stream) csv += chunk.toString('utf8');
    assert.equal(csv.trim().split('\n').length,4001);
    await page.selectOption('#matrixMetric','row_share');
    assert.equal(await page.evaluate(() => charts.matrix.getOption().visualMap[0].max), 100);
    await page.locator('#types').scrollIntoViewIfNeeded();
    await page.waitForTimeout(350);
    const bar = await page.evaluate(() => {
      const name=charts.types.getOption().yAxis[0].data[9];
      const value=charts.types.getOption().series[0].data[9];
      const [x,y]=charts.types.convertToPixel({seriesIndex:0},[value/2,name]);
      const rect=document.querySelector('#types').getBoundingClientRect();
      return {name,x:rect.left+x,y:rect.top+y};
    });
    await page.mouse.click(bar.x,bar.y);
    await page.waitForFunction(name => document.querySelector('#issue_type').value === name, bar.name);
    await loaded();
    assert.ok(await page.evaluate(() => current.total < 4000));
    await page.click('#reset'); await loaded();
    assert.equal(await page.locator('#total').innerText(),'12,010');
    await page.selectOption('#year','2025');
    await page.selectOption('#category','未知');
    await loaded();
    assert.equal(await page.locator('#total').innerText(),'0');
    assert.equal(await page.locator('#amount').innerText(),'无样本');
    assert.match(await page.locator('#rows').innerText(),/没有样本/);
    await page.click('#reset'); await loaded();
    if(process.env.SCREENSHOT_DIR){
      await page.screenshot({path:process.env.SCREENSHOT_DIR+'/dashboard-desktop.png',fullPage:true});
    }
    await page.setViewportSize({width:390,height:844});
    await page.waitForTimeout(300);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    if(process.env.SCREENSHOT_DIR){
      await page.screenshot({path:process.env.SCREENSHOT_DIR+'/dashboard-mobile.png',fullPage:true});
    }
    assert.deepEqual(errors,[]); assert.deepEqual(external,[]);
    console.log('浏览器验证通过：七图、筛选、分页、CSV、图表下钻、空样本、重置、移动布局；无外部资源请求或脚本错误。');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode=1;});
