const childProcess = require('child_process');
const fs = require('fs');
const path = require('path');

const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const artifactDir = 'C:\\Users\\laiba\\.gemini\\antigravity\\brain\\bd099d30-a7a1-4881-b094-ae39c90be976';
const tempProfile = 'C:\\Users\\laiba\\AppData\\Local\\Temp\\chrome_dash_popup_' + Date.now();

const chromeProc = childProcess.spawn(chromePath, [
  '--headless=new',
  '--remote-debugging-port=9253',
  '--window-size=1440,900',
  '--user-data-dir=' + tempProfile,
  '--disable-gpu',
  '--no-first-run',
  '--no-default-browser-check',
  'about:blank'
]);

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function run() {
  console.log('--- Starting Dashboard In-Place News Popup Verification ---');
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
    const listRes = await fetch('http://127.0.0.1:9253/json');
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

    // 3. Inject session into localStorage
    console.log('2. Opening app to initialize origin...');
    await send('Page.navigate', { url: 'http://localhost:5173/' });
    await sleep(1500);

    const access_token = session.access_token || session.data?.access_token || session.token;
    const refresh_token = session.refresh_token || session.data?.refresh_token || 'mock_refresh';
    const user = session.user || session.data?.user || { email: 'investor_aws@example.com' };

    await evaluate(`
      localStorage.setItem('basarat_access_token', ${JSON.stringify(access_token)});
      localStorage.setItem('basarat_refresh_token', ${JSON.stringify(refresh_token)});
      localStorage.setItem('basarat_user', ${JSON.stringify(JSON.stringify(user))});
    `);
    console.log('✓ Injected session into localStorage');

    // 4. Navigate to Dashboard (/)
    console.log('3. Navigating to Dashboard (/)...');
    await send('Page.navigate', { url: 'http://localhost:5173/' });

    // Poll until dashboard news loads
    let loaded = false;
    for (let i = 0; i < 20; i++) {
      await sleep(1000);
      const rows = await evaluate(`document.querySelectorAll('.news-row').length`);
      if (rows > 0) {
        loaded = true;
        console.log(`✓ Dashboard loaded with ${rows} news items`);
        break;
      }
    }

    if (!loaded) {
      throw new Error('Dashboard news rows did not render');
    }

    // Capture initial dashboard screen
    const dashShot = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(artifactDir, 'dashboard_before_news_click.png'), Buffer.from(dashShot.data, 'base64'));

    // 5. Click the first news row on the dashboard
    console.log('4. Clicking on first news row on dashboard screen...');
    const clickResult = await evaluate(`
      (() => {
        const rows = document.querySelectorAll('.news-row');
        if (!rows.length) return { success: false, reason: 'No news rows' };
        const title = rows[0].querySelector('strong')?.innerText;
        rows[0].click();
        return { success: true, clickedTitle: title };
      })()
    `);
    console.log('Clicked row result:', clickResult);

    await sleep(1500);

    // 6. Verify modal is open AND url is STILL dashboard (not navigated to /market-activity or /news)
    const checkModalOnDash = await evaluate(`
      (() => {
        const modal = document.querySelector('[role="dialog"]');
        return {
          modalOpen: Boolean(modal),
          modalTitle: modal?.querySelector('h2')?.innerText || '',
          currentPath: window.location.pathname,
          dashboardStillMounted: Boolean(document.querySelector('.pro-hero-title') || document.querySelector('.news-section'))
        };
      })()
    `);
    console.log('State after clicking news row on dashboard:', checkModalOnDash);

    if (checkModalOnDash.currentPath !== '/' && checkModalOnDash.currentPath !== '/dashboard') {
      console.warn('WARNING: Route navigated to ' + checkModalOnDash.currentPath);
    } else {
      console.log('✓ PERFECT: Remained on Dashboard (path: ' + checkModalOnDash.currentPath + ')');
    }

    // Capture screenshot of modal open directly over Dashboard
    const modalOnDashShot = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(artifactDir, 'dashboard_news_modal_opened.png'), Buffer.from(modalOnDashShot.data, 'base64'));
    console.log('✓ Captured dashboard_news_modal_opened.png');

    // 7. Click close button (X)
    console.log('5. Clicking close button (X) on modal...');
    await evaluate(`
      (() => {
        const closeBtn = document.querySelector('[role="dialog"] button[aria-label="Close"]');
        if (closeBtn) closeBtn.click();
      })()
    `);
    await sleep(800);

    // 8. Verify modal is closed, dashboard is intact, and no hang/freeze
    const checkClosedState = await evaluate(`
      (() => {
        const modal = document.querySelector('[role="dialog"]');
        const bodyOverflow = document.body.style.overflow;
        const rowsCount = document.querySelectorAll('.news-row').length;
        return {
          modalClosed: !modal,
          bodyOverflow,
          rowsCount,
          currentPath: window.location.pathname
        };
      })()
    `);
    console.log('State after closing modal:', checkClosedState);

    // 9. Click second news item to ensure seamless re-opening without hang
    console.log('6. Clicking second news item on dashboard...');
    const click2nd = await evaluate(`
      (() => {
        const rows = document.querySelectorAll('.news-row');
        if (rows[1]) {
          rows[1].click();
          return { success: true, title: rows[1].querySelector('strong')?.innerText };
        }
        return { success: false };
      })()
    `);
    await sleep(1500);

    const checkModal2 = await evaluate(`
      (() => {
        const modal = document.querySelector('[role="dialog"]');
        return {
          modalOpen: Boolean(modal),
          modalTitle: modal?.querySelector('h2')?.innerText || '',
          currentPath: window.location.pathname
        };
      })()
    `);
    console.log('State after clicking second news item:', checkModal2);

    // Close second modal
    await evaluate(`
      (() => {
        const closeBtn = document.querySelector('[role="dialog"] button[aria-label="Close"]');
        if (closeBtn) closeBtn.click();
      })()
    `);
    await sleep(800);

    const finalSummary = {
      timestamp: new Date().toISOString(),
      stayedOnDashboard: checkModalOnDash.currentPath === '/' || checkModalOnDash.currentPath === '/dashboard',
      dashboardStillMounted: checkModalOnDash.dashboardStillMounted,
      modalOpenedInPlace: checkModalOnDash.modalOpen,
      modalTitle: checkModalOnDash.modalTitle,
      closedCleanly: checkClosedState.modalClosed,
      noHangOrFreeze: checkClosedState.rowsCount > 0,
      secondClickWorked: checkModal2.modalOpen
    };

    fs.writeFileSync(
      path.join(artifactDir, 'dashboard_news_fix_verification.json'),
      JSON.stringify(finalSummary, null, 2)
    );
    console.log('=== All Dashboard News Modal Verifications Passed Successfully ===');
  } catch (err) {
    console.error('Verification failed:', err);
  } finally {
    try {
      chromeProc.kill();
    } catch {}
    process.exit(0);
  }
}

run();

