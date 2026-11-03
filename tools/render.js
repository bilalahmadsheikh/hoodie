// Render the viewer with headless Chromium: node tools/render.js <glb> <outdir> [views...]
// Set THREE_DIR to a local node_modules/three when the CDN is unreachable.
const { chromium } = require('playwright');
const path = require('path'), fs = require('fs');
(async () => {
  const [glb, outdir, ...views] = process.argv.slice(2);
  const viewer = path.resolve(__dirname, '../viewer/index.html');
  const threeDir = process.env.THREE_DIR;
  fs.mkdirSync(outdir, { recursive: true });
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 900, height: 1000 }, deviceScaleFactor: Number(process.env.DPR || 1) });
  page.on('console', m => { if (m.type() === 'error') console.log('console:', m.text()); });
  page.on('pageerror', e => console.log('pageerror:', e.message));
  await page.route('**/*', (route) => {
    const url = route.request().url();
    const m = url.match(/three@[\d.]+\/(.*)$/);
    if (m && threeDir) return route.fulfill({ path: path.join(threeDir, m[1]), contentType: 'application/javascript' });
    if (new URL(url).pathname.endsWith('.glb')) return route.fulfill({ path: path.resolve(glb), contentType: 'model/gltf-binary' });
    if (url.startsWith('http://hoodie.local/')) return route.fulfill({ path: viewer, contentType: 'text/html' });
    return route.abort();
  });
  for (const v of (views.length ? views : ['front', 'three', 'side', 'back', 'detail'])) {
    await page.goto('http://hoodie.local/index.html?view=' + v + '&model=model.glb');
    await page.waitForFunction(() => window.__ready === true, null, { timeout: 120000 });
    const url = await page.evaluate(() => window.__still());
    fs.writeFileSync(path.join(outdir, v + '.png'), Buffer.from(url.split(',')[1], 'base64'));
    console.log('rendered', v);
  }
  await browser.close();
})();
