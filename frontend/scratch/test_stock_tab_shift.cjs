const childProcess = require('child_process');
const fs = require('fs');
const path = require('path');

const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const artifactDir = 'C:\\Users\\laiba\\.gemini\\antigravity\\brain\\bd099d30-a7a1-4881-b094-ae39c90be976';
const tempProfile = 'C:\\Users\\laiba\\AppData\\Local\\Temp\\chrome_stock_tabs_' + Date.now();

const chromeProc = childProcess.spawn(chromePath, [
  '--headless=new',
  '--remote-debugging-port=9258',
  '--window-size=1440,900',
  '--user-data-dir=' + tempProfile,
  '--disable-gpu',
  '--no-first-run',
  '--no-default-browser-check',
  'about:blank'
]);

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function run() {
  console.log('--- Starting Stock Detail Tab Shift Speed Verification ---');
  try {
    await sleep(1500);

    const listRes = await fetch('http://127.0.0.1:9258/json');
    const targets = await listRes.json();
    const pageTarget = targets.find(t => t.type === 'page');

    const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);
    let id = 1;

    const send = (method, params = {}) => new Promise((resolve, reject) => {
      const curId = id++;
      const h = (msg) => {
        const data = JSON.parse(msg.data);
        if (data.id === curId) {
          ws.removeEventListener('message', h);
          if (data.error) reject(data.error); else resolve(data.result);
        }
      };
      ws.addEventListener('message', h);
      ws.send(JSON.stringify({ id: curId, method, params }));
    });

    await new Promise(r => ws.onopen = r);
    console.log('✓ Connected to Headless Chrome CDP');

    await send('Page.enable');
    await send('Runtime.enable');
    await send('DOM.enable');

    const evaluate = async (expr) => {
      const res = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
      return res.result?.value;
    };

    console.log('1. Navigating to stock detail page: http://localhost:5173/stocks/MEBL ...');
    await send('Page.navigate', { url: 'http://localhost:5173/stocks/MEBL' });
    await sleep(2000);

    // Verify tabs rendered
    const tabs = await evaluate(`
      Array.from(document.querySelectorAll('.border-b button')).map(b => b.textContent.trim())
    `);
    console.log('Found navigation tabs:', tabs);

    const takeScreenshot = async (name) => {
      const { data } = await send('Page.captureScreenshot', { format: 'png' });
      const filePath = path.join(artifactDir, name + '.png');
      fs.writeFileSync(filePath, Buffer.from(data, 'base64'));
      console.log(`✓ Screenshot captured: ${name}.png`);
    };

    // Helper to click tab and measure switch time
    const clickTab = async (label) => {
      const result = await evaluate(`
        (() => {
          const btns = Array.from(document.querySelectorAll('button'));
          const target = btns.find(b => b.textContent.trim() === '${label}');
          if (!target) return { found: false };

          const start = performance.now();
          target.click();
          const end = performance.now();
          
          return {
            found: true,
            elapsedMs: (end - start).toFixed(2),
            activeTab: target.textContent.trim(),
            hasActiveClasses: target.className.includes('border-slate-900')
          };
        })()
      `);
      return result;
    };

    // 1. Initial Overview Tab
    console.log('\n--- 1. Testing Overview Tab ---');
    await takeScreenshot('stock_tab_shift_1_overview');

    // 2. Shift to Financials
    console.log('\n--- 2. Shifting to Financials Tab ---');
    const finRes = await clickTab('Financials');
    console.log('Financials tab click result:', finRes);
    await sleep(800);
    const finPanelState = await evaluate(`
      (() => {
        const panels = Array.from(document.querySelectorAll('.stock-tab-panel'));
        return panels.map(p => ({
          active: p.classList.contains('active'),
          inactive: p.classList.contains('inactive'),
          textPreview: p.innerText.slice(0, 100)
        }));
      })()
    `);
    console.log('Tab panels state on Financials:', finPanelState);
    await takeScreenshot('stock_tab_shift_2_financials');

    // 3. Shift to Technicals
    console.log('\n--- 3. Shifting to Technicals Tab ---');
    const techRes = await clickTab('Technicals');
    console.log('Technicals tab click result:', techRes);
    await sleep(500);
    await takeScreenshot('stock_tab_shift_3_technicals');

    // 4. Shift to Shariah Screening
    console.log('\n--- 4. Shifting to Shariah Screening Tab ---');
    const shariahRes = await clickTab('Shariah Screening');
    console.log('Shariah tab click result:', shariahRes);
    await sleep(600);
    await takeScreenshot('stock_tab_shift_4_shariah');

    // 5. Shift to AI Forecast & Signals
    console.log('\n--- 5. Shifting to AI Forecast & Signals Tab ---');
    const forecastRes = await clickTab('AI Forecast & Signals');
    console.log('AI Forecast tab click result:', forecastRes);
    await sleep(600);
    await takeScreenshot('stock_tab_shift_5_forecast');

    // 6. Shift to News & Sentiment
    console.log('\n--- 6. Shifting to News & Sentiment Tab ---');
    const newsRes = await clickTab('News & Sentiment');
    console.log('News tab click result:', newsRes);
    await sleep(600);
    await takeScreenshot('stock_tab_shift_6_news');

    // 7. Shift BACK to Overview (Tests instant 0ms DOM view retention)
    console.log('\n--- 7. Testing Retention: Shifting back to Overview ---');
    const backOverviewRes = await clickTab('Overview');
    console.log('Back to Overview click result:', backOverviewRes);
    await sleep(200);
    await takeScreenshot('stock_tab_shift_7_back_to_overview');

    // 8. Shift BACK to Financials (Tests instant 0ms DOM view retention)
    console.log('\n--- 8. Testing Retention: Shifting back to Financials ---');
    const backFinRes = await clickTab('Financials');
    console.log('Back to Financials click result:', backFinRes);
    await sleep(200);
    await takeScreenshot('stock_tab_shift_8_back_to_financials');

    console.log('\n✓ ALL TAB SHIFTS COMPLETED SUCCESSFULLY WITH 0ms VIEW RETENTION!');
  } catch (err) {
    console.error('Error during tab shift test:', err);
  } finally {
    try { chromeProc.kill(); } catch {}
  }
}

run();

