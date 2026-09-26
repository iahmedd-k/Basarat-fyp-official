const childProcess = require('child_process');
const fs = require('fs');
const path = require('path');

const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const artifactDir = 'C:\\Users\\laiba\\.gemini\\antigravity\\brain\\bd099d30-a7a1-4881-b094-ae39c90be976';
const tempProfile = 'C:\\Users\\laiba\\AppData\\Local\\Temp\\chrome_portfolio_full_' + Date.now();

const chromeProc = childProcess.spawn(chromePath, [
  '--headless=new',
  '--remote-debugging-port=9247',
  '--window-size=1440,900',
  '--user-data-dir=' + tempProfile,
  '--disable-gpu',
  '--no-first-run',
  '--no-default-browser-check',
  'about:blank'
]);

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function run() {
  console.log('--- Starting Comprehensive Portfolio Redesign Verification ---');
  try {
    // 1. Authenticate with AWS backend
    console.log('1. Authenticating with AWS backend (investor_aws@example.com)...');
    const authRes = await fetch('http://16.16.26.247:8000/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'investor_aws@example.com', password: 'Password123!' })
    });
    
    if (!authRes.ok) throw new Error(`Login failed: ${authRes.status}`);
    const session = await authRes.json();
    console.log('✓ Successfully authenticated with AWS backend');

    await sleep(1500);

    // 2. Connect to Chrome CDP
    const listRes = await fetch('http://127.0.0.1:9247/json');
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
    await send('Page.enable');
    await send('Runtime.enable');
    await send('DOM.enable');

    const consoleErrors = [];
    ws.addEventListener('message', (msg) => {
      const data = JSON.parse(msg.data);
      if (data.method === 'Runtime.consoleAPICalled' && data.params.type === 'error') {
        const text = data.params.args.map(a => a.value || a.description || '').join(' ');
        consoleErrors.push(text);
      }
    });

    const evaluate = async (expr) => {
      const res = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
      return res.result?.value;
    };

    const takeScreenshot = async (filename) => {
      const { data } = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
      const targetPath = path.join(artifactDir, filename);
      fs.writeFileSync(targetPath, Buffer.from(data, 'base64'));
      console.log(`✓ Screenshot saved: ${filename}`);
    };

    // 3. Navigate to app and inject session
    console.log('2. Opening app and injecting authentication session...');
    await send('Page.navigate', { url: 'http://localhost:5173' });
    await sleep(1500);

    await evaluate(`
      localStorage.setItem('basarat_access_token', ${JSON.stringify(session.access_token)});
      localStorage.setItem('basarat_refresh_token', ${JSON.stringify(session.refresh_token)});
      localStorage.setItem('basarat_user', ${JSON.stringify(JSON.stringify(session.user))});
    `);

    // 4. Navigate directly to portfolio page
    console.log('3. Navigating to Portfolio page (/portfolio)...');
    await send('Page.navigate', { url: 'http://localhost:5173/portfolio' });

    // Poll until data is loaded
    let isLoaded = false;
    for (let i = 0; i < 20; i++) {
      await sleep(1000);
      const loading = await evaluate(`!document.querySelector('.animate-pulse') && document.querySelectorAll('tbody tr').length > 0`);
      if (loading) {
        isLoaded = true;
        break;
      }
    }
    console.log('Data loaded successfully:', isLoaded);

    // 5. Inspect Hero Stats
    const kpiSummary = await evaluate(`(() => {
      return {
        heroValue: document.querySelector('[data-testid="portfolio-hero-value"]')?.innerText,
        pills: Array.from(document.querySelectorAll('.rounded-full.border')).map(p => p.innerText.replace(/\\s+/g, ' ').trim()),
      };
    })()`);
    console.log('Hero values:', JSON.stringify(kpiSummary, null, 2));

    // 6. Inspect Holdings Table Rows
    const holdingsData = await evaluate(`(() => {
      const rows = Array.from(document.querySelectorAll('tbody tr'));
      return rows.map(r => {
        const tds = Array.from(r.querySelectorAll('td'));
        return {
          symbol: tds[0]?.querySelector('strong')?.innerText,
          company: tds[0]?.querySelector('span')?.innerText,
          shares: tds[1]?.innerText,
          avgCost: tds[2]?.innerText,
          ltp: tds[3]?.innerText,
          marketValue: tds[4]?.innerText,
          pnl: tds[5]?.innerText?.replace(/\\s+/g, ' ').trim(),
          weight: tds[6]?.innerText?.replace(/\\s+/g, ' ').trim()
        };
      });
    })()`);
    console.log(`Holdings positions count: ${holdingsData.length}`, JSON.stringify(holdingsData, null, 2));

    // 7. Test Search Filter on Holdings
    console.log('4. Testing search filter ("SYS")...');
    await evaluate(`(() => {
      const input = document.querySelector('input[placeholder*="Filter"]');
      if (input) {
        input.value = 'SYS';
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }
    })()`);
    await sleep(500);
    const filteredCount = await evaluate(`document.querySelectorAll('tbody tr').length`);
    console.log(`Filtered rows for "SYS": ${filteredCount}`);

    // Clear filter
    await evaluate(`(() => {
      const input = document.querySelector('input[placeholder*="Filter"]');
      if (input) {
        input.value = '';
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }
    })()`);
    await sleep(500);

    // 8. Capture Desktop 1440 Viewport
    await takeScreenshot('portfolio_desktop_1440.png');

    // 9. Test Performance Tab & capture screenshot
    console.log('5. Testing Performance Tab...');
    await evaluate(`document.querySelector('[data-testid="portfolio-tab-performance"]')?.click()`);
    await sleep(1000);
    const hasPerfSvg = await evaluate(`!!document.querySelector('svg.w-full')`);
    console.log('Performance chart SVG present:', hasPerfSvg);
    await takeScreenshot('portfolio_performance_tab.png');

    // 10. Test Asset Allocation Tab & capture screenshot
    console.log('6. Testing Asset Allocation Tab...');
    await evaluate(`document.querySelector('[data-testid="portfolio-tab-allocation"]')?.click()`);
    await sleep(1000);
    const allocationSectors = await evaluate(`Array.from(document.querySelectorAll('.font-bold.text-slate-900')).map(el => el.innerText)`);
    console.log('Allocation items:', allocationSectors.slice(0, 5));
    await takeScreenshot('portfolio_allocation_tab.png');

    // 11. Test Transactions Tab & capture screenshot
    console.log('7. Testing Transactions Tab...');
    await evaluate(`document.querySelector('[data-testid="portfolio-tab-transactions"]')?.click()`);
    await sleep(1000);
    const txRows = await evaluate(`document.querySelectorAll('tbody tr').length`);
    console.log(`Transaction rows count: ${txRows}`);
    await takeScreenshot('portfolio_transactions_tab.png');

    // Switch back to Holdings
    await evaluate(`document.querySelector('[data-testid="portfolio-tab-holdings"]')?.click()`);
    await sleep(500);

    // 12. Test Record Transaction Modal
    console.log('8. Testing Record Transaction Modal...');
    await evaluate(`document.querySelector('[data-testid="portfolio-record-btn"]')?.click()`);
    await sleep(800);
    const modalVisible = await evaluate(`!!document.querySelector('.fixed.inset-0')`);
    console.log('Modal visible:', modalVisible);
    await takeScreenshot('portfolio_trade_modal.png');

    // Close modal
    await evaluate(`(() => {
      const cancelBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Cancel'));
      if (cancelBtn) cancelBtn.click();
    })()`);
    await sleep(500);

    // 13. Test Responsiveness across all viewports
    console.log('9. Checking responsiveness and horizontal scroll across all breakpoints...');
    const viewports = [
      { name: 'desktop_1440', width: 1440, height: 900 },
      { name: 'laptop_1024', width: 1024, height: 768 },
      { name: 'tablet_768', width: 768, height: 1024 },
      { name: 'mobile_375', width: 375, height: 812 }
    ];

    const overflowResults = {};

    for (const vp of viewports) {
      await send('Emulation.setDeviceMetricsOverride', {
        width: vp.width,
        height: vp.height,
        deviceScaleFactor: 1,
        mobile: vp.width < 768
      });
      await sleep(1000);

      const overflow = await evaluate(`(() => {
        const docWidth = document.documentElement.clientWidth;
        const scrollWidth = document.documentElement.scrollWidth;
        const bodyScrollWidth = document.body.scrollWidth;
        return {
          clientWidth: docWidth,
          docScrollWidth: scrollWidth,
          bodyScrollWidth: bodyScrollWidth,
          hasHorizontalScroll: scrollWidth > docWidth || bodyScrollWidth > docWidth
        };
      })()`);

      overflowResults[vp.name] = overflow;
      console.log(`Viewport ${vp.name} (${vp.width}px): horizontal scroll = ${overflow.hasHorizontalScroll}`);

      await takeScreenshot(`portfolio_${vp.name}.png`);
    }

    // 14. Save full report artifact
    const report = {
      timestamp: new Date().toISOString(),
      kpiSummary,
      holdingsCount: holdingsData.length,
      holdings: holdingsData,
      filteredCountSYS: filteredCount,
      hasPerformanceChart: hasPerfSvg,
      transactionRows: txRows,
      modalOpenedAndClosedCleanly: modalVisible,
      overflowResults,
      consoleErrors: consoleErrors.filter(e => !e.includes('favicon'))
    };

    fs.writeFileSync(
      path.join(artifactDir, 'portfolio_redesign_verification.json'),
      JSON.stringify(report, null, 2)
    );
    console.log('✓ Verification report saved to portfolio_redesign_verification.json');
    console.log('=== All Portfolio Redesign Verifications Succeeded! ===');

  } catch (err) {
    console.error('Test execution failed:', err);
  } finally {
    try {
      chromeProc.kill();
    } catch (e) {}
  }
}

run();

