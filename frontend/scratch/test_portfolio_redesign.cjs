const childProcess = require('child_process');
const fs = require('fs');
const path = require('path');

const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const artifactDir = 'C:\\Users\\laiba\\.gemini\\antigravity\\brain\\bd099d30-a7a1-4881-b094-ae39c90be976';
const tempProfile = 'C:\\Users\\laiba\\AppData\\Local\\Temp\\chrome_portfolio_profile_' + Date.now();

const chromeProc = childProcess.spawn(chromePath, [
  '--headless=new',
  '--remote-debugging-port=9246',
  '--window-size=1440,900',
  '--user-data-dir=' + tempProfile,
  '--disable-gpu',
  '--no-first-run',
  '--no-default-browser-check',
  'about:blank'
]);

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function run() {
  console.log('Testing Portfolio Redesign with AWS backend...');
  try {
    // 1. Authenticate with AWS backend
    console.log('Logging in to AWS backend...');
    const authRes = await fetch('http://16.16.26.247:8000/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'investor_aws@example.com', password: 'Password123!' })
    });
    
    if (!authRes.ok) {
      throw new Error(`Login failed: ${authRes.status} ${await authRes.text()}`);
    }
    const session = await authRes.json();
    console.log('Login successful for user:', session.user?.email || 'authenticated');

    await sleep(1500);

    // 2. Connect to Chrome CDP
    const listRes = await fetch('http://127.0.0.1:9246/json');
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

    const takeScreenshot = async (filePath) => {
      const { data } = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
      fs.writeFileSync(filePath, Buffer.from(data, 'base64'));
      console.log('Screenshot saved:', path.basename(filePath));
    };

    // 3. Navigate to app and set auth session
    console.log('Navigating to http://localhost:5173...');
    await send('Page.navigate', { url: 'http://localhost:5173' });
    await sleep(2000);

    await evaluate(`
      localStorage.setItem('basarat_access_token', ${JSON.stringify(session.access_token)});
      localStorage.setItem('basarat_refresh_token', ${JSON.stringify(session.refresh_token)});
      localStorage.setItem('basarat_user', ${JSON.stringify(JSON.stringify(session.user))});
    `);

    // 4. Navigate directly to portfolio page
    console.log('Navigating to http://localhost:5173/portfolio...');
    await send('Page.navigate', { url: 'http://localhost:5173/portfolio' });
    await sleep(2500);

    // 5. Verify page title and KPI elements
    const pageVerification = await evaluate(`(() => {
      const heading = document.querySelector('h1')?.innerText;
      const kpis = Array.from(document.querySelectorAll('.portfolio-kpi-card')).map(c => ({
        label: c.querySelector('.kpi-label')?.innerText,
        value: c.querySelector('.kpi-value')?.innerText
      }));
      const tabs = Array.from(document.querySelectorAll('.portfolio-tab-btn')).map(b => b.innerText.trim());
      const hasRecordBtn = !!document.querySelector('.record-trade-btn');
      const tableHeaders = Array.from(document.querySelectorAll('.holdings-table th')).map(th => th.innerText.trim());
      const holdingRows = document.querySelectorAll('.holding-row').length;

      return {
        heading,
        kpis,
        tabs,
        hasRecordBtn,
        tableHeaders,
        holdingRows
      };
    })()`);

    console.log('Portfolio page verification:', JSON.stringify(pageVerification, null, 2));

    // 6. Test Tab Switching
    console.log('Testing Tab: Performance & Chart...');
    await evaluate(`(() => {
      const btns = Array.from(document.querySelectorAll('.portfolio-tab-btn'));
      const perfBtn = btns.find(b => b.innerText.includes('Performance'));
      if (perfBtn) perfBtn.click();
    })()`);
    await sleep(800);
    const perfChartExists = await evaluate(`!!document.querySelector('.portfolio-chart-svg')`);
    console.log('Performance chart rendered:', perfChartExists);

    console.log('Testing Tab: Asset Allocation...');
    await evaluate(`(() => {
      const btns = Array.from(document.querySelectorAll('.portfolio-tab-btn'));
      const allocBtn = btns.find(b => b.innerText.includes('Asset Allocation'));
      if (allocBtn) allocBtn.click();
    })()`);
    await sleep(800);
    const allocSections = await evaluate(`Array.from(document.querySelectorAll('.allocation-card-header h3')).map(h => h.innerText)`);
    console.log('Allocation cards rendered:', allocSections);

    console.log('Testing Tab: Transactions Log...');
    await evaluate(`(() => {
      const btns = Array.from(document.querySelectorAll('.portfolio-tab-btn'));
      const txBtn = btns.find(b => b.innerText.includes('Transactions'));
      if (txBtn) txBtn.click();
    })()`);
    await sleep(800);
    const txHeaders = await evaluate(`Array.from(document.querySelectorAll('.tx-table th')).map(th => th.innerText)`);
    console.log('Transactions table headers:', txHeaders);

    // Switch back to Holdings tab
    await evaluate(`(() => {
      const btns = Array.from(document.querySelectorAll('.portfolio-tab-btn'));
      const hBtn = btns.find(b => b.innerText.includes('Holdings'));
      if (hBtn) hBtn.click();
    })()`);
    await sleep(800);

    // 7. Test Record Transaction Modal
    console.log('Testing Record Transaction Modal...');
    await evaluate(`document.querySelector('.record-trade-btn')?.click()`);
    await sleep(500);
    const modalVisible = await evaluate(`!!document.querySelector('.trade-modal-container')`);
    const modalTitle = await evaluate(`document.querySelector('.trade-modal-header h2')?.innerText`);
    console.log('Modal visible:', modalVisible, 'Title:', modalTitle);
    
    // Close modal
    await evaluate(`document.querySelector('.trade-modal-btn-cancel')?.click()`);
    await sleep(500);
    const modalClosed = await evaluate(`!document.querySelector('.trade-modal-container')`);
    console.log('Modal cleanly closed:', modalClosed);

    // 8. Viewport and Responsiveness Verification
    const viewports = [
      { name: 'desktop_1440', width: 1440, height: 900 },
      { name: 'laptop_1024', width: 1024, height: 768 },
      { name: 'tablet_768', width: 768, height: 1024 },
      { name: 'mobile_375', width: 375, height: 812 }
    ];

    const overflowResults = {};

    for (const vp of viewports) {
      console.log(`Setting viewport: ${vp.width}x${vp.height} (${vp.name})...`);
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
      console.log(`Viewport ${vp.name} overflow check:`, overflow);

      const shotPath = path.join(artifactDir, `portfolio_${vp.name}.png`);
      await takeScreenshot(shotPath);
    }

    console.log('All responsive screenshots captured successfully.');
    console.log('Console Errors encountered:', consoleErrors.filter(e => !e.includes('favicon')));

    // Write test summary report artifact
    const summaryData = {
      timestamp: new Date().toISOString(),
      pageVerification,
      perfChartExists,
      allocSections,
      txHeaders,
      modalOpenedAndClosedCleanly: modalVisible && modalClosed,
      overflowResults,
      consoleErrors: consoleErrors.filter(e => !e.includes('favicon'))
    };

    fs.writeFileSync(
      path.join(artifactDir, 'portfolio_redesign_test_results.json'),
      JSON.stringify(summaryData, null, 2)
    );
    console.log('Test summary written to portfolio_redesign_test_results.json');

  } catch (err) {
    console.error('Test execution failed:', err);
  } finally {
    try {
      chromeProc.kill();
    } catch (e) {}
  }
}

run();

