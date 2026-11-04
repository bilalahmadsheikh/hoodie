// Render production/tech_pack.html to a PDF (and page previews):
//   node tools/make_tech_pack.js [previewDir]
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const html = path.resolve(__dirname, '../production/tech_pack.html');
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1123, height: 794 } });
  await page.goto('file://' + html, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({
    path: path.resolve(__dirname, '../production/GIK_hoodie_tech_pack.pdf'),
    width: '297mm', height: '210mm', printBackground: true,
  });
  const out = process.argv[2];
  if (out) {
    const pages = await page.$$('section.page');
    for (let i = 0; i < pages.length; i++) {
      await pages[i].screenshot({ path: path.join(out, `page${i + 1}.png`) });
    }
  }
  console.log('pdf written');
  await browser.close();
})();
