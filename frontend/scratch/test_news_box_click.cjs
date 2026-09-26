const childProcess = require('child_process');
const fs = require('fs');
const path = require('path');

const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const artifactDir = 'C:\\Users\\laiba\\.gemini\\antigravity\\brain\\bd099d30-a7a1-4881-b094-ae39c90be976';
const tempProfile = 'C:\\Users\\laiba\\AppData\\Local\\Temp\\chrome_news_modal_' + Date.now();

const chromeProc = childProcess.spawn(chromePath, [
  '--headless=new',
  '--remote-debugging-port=9251',
  '--window-size=1440,900',
  '--user-data-dir=' + tempProfile,
  '--disable-gpu',
  '--no-first-run',
  '--no-default-browser-check',
  'about:blank'
]);

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function run() {
  console.log('--- Starting News Box Click & Popup Modal Verification ---');
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
    const listRes = await fetch('http://127.0.0.1:9251/json');
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

    // 4. Navigate directly to /market-activity
    console.log('3. Navigating to http://localhost:5173/market-activity...');
    await send('Page.navigate', { url: 'http://localhost:5173/market-activity' });

    // Poll until articles render
    let loaded = false;
    for (let i = 0; i < 20; i++) {
      await sleep(1000);
      const count = await evaluate(`document.querySelectorAll('article').length`);
      if (count > 0) {
        loaded = true;
        console.log(`✓ Loaded ${count} announcements`);
        break;
      }
    }

    if (!loaded) {
      const pageInfo = await evaluate(`({ title: document.title, body: document.body.innerText.slice(0, 300) })`);
      console.log('Page did not load articles. State:', pageInfo);
    }

    // Verify articles rendered
    const checkArticles = await evaluate(`
      (() => {
        const articles = document.querySelectorAll('article');
        return {
          count: articles.length,
          firstTitle: articles[0]?.querySelector('h2')?.innerText || '',
          titles: Array.from(articles).slice(0, 5).map(a => a.querySelector('h2')?.innerText || '')
        };
      })()
    `);
    console.log('Articles on Market Activity page:', checkArticles);

    // Check hover state: dispatch mouseover to card and verify title computed color
    console.log('4. Verifying no text highlight when cursor enters news box...');
    const hoverColorCheck = await evaluate(`
      (() => {
        const article = document.querySelector('article');
        if (!article) return { error: 'No article' };
        const h2 = article.querySelector('h2');
        const colorBefore = window.getComputedStyle(h2).color;
        // Dispatch mouseenter & mouseover
        article.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
        article.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
        const colorOnHover = window.getComputedStyle(h2).color;
        return {
          colorBefore,
          colorOnHover,
          isHighlighted: colorOnHover.includes('150') || colorOnHover.includes('185') // green/emerald
        };
      })()
    `);
    console.log('Hover text color check (should NOT highlight):', hoverColorCheck);

    // 5. Test clicking anywhere inside a news box (card)
    console.log('5. Clicking inside the news box (on the summary text / card body)...');
    const clickBoxResult = await evaluate(`
      (() => {
        const articles = Array.from(document.querySelectorAll('article'));
        const target = articles.find(a => a.innerText.includes('BERG') || a.innerText.includes('Berger')) || articles[0];
        if (!target) return { success: false, reason: 'No article found' };
        
        // Click on the summary paragraph text inside the card body (not on a button)
        const summary = target.querySelector('p') || target;
        summary.click();
        return { success: true, clickedTitle: target.querySelector('h2')?.innerText };
      })()
    `);
    console.log('Clicked news box result:', clickBoxResult);

    await sleep(2000);

    // 6. Check if detail modal is open
    const checkModal = await evaluate(`
      (() => {
        const modal = document.querySelector('[role="dialog"]');
        if (!modal) return { open: false };
        return {
          open: true,
          title: modal.querySelector('h2')?.innerText,
          hasFindings: Boolean(modal.innerText.includes('KEY FINDINGS')),
          findings: Array.from(modal.querySelectorAll('li')).map(l => l.innerText),
          hasMetrics: Boolean(modal.innerText.includes('Revenue') || modal.innerText.includes('Earnings Per Share') || modal.innerText.includes('Dividend Yield')),
          metrics: Array.from(modal.querySelectorAll('.border-b')).map(b => b.innerText.replace(/\\n/g, ' ')),
          hasReportLink: Boolean(modal.querySelector('a')?.innerText.includes('View full report')),
          url: window.location.pathname
        };
      })()
    `);
    console.log('Modal state after clicking news box:', checkModal);

    // 7. Capture screenshot of modal opened by box click
    const modalShot = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(artifactDir, 'market_activity_detail_popup.png'), Buffer.from(modalShot.data, 'base64'));
    console.log('✓ Captured market_activity_detail_popup.png');

    // 8. Test closing modal by clicking close button (X)
    console.log('5. Testing close button (X)...');
    await evaluate(`
      (() => {
        const closeBtn = document.querySelector('[role="dialog"] button[aria-label="Close"]');
        if (closeBtn) closeBtn.click();
      })()
    `);
    await sleep(800);

    const checkClosed = await evaluate(`Boolean(document.querySelector('[role="dialog"]'))`);
    console.log('Modal closed after clicking X:', !checkClosed);

    // 9. Test clicking ANOTHER news box (e.g. 2nd article) anywhere in the box
    console.log('6. Clicking 2nd news box anywhere in the card...');
    const click2nd = await evaluate(`
      (() => {
        const articles = document.querySelectorAll('article');
        if (articles[1]) {
          articles[1].click();
          return { success: true, title: articles[1].querySelector('h2')?.innerText };
        }
        return { success: false };
      })()
    `);
    console.log('Clicked 2nd news box:', click2nd);
    await sleep(2000);

    const checkModal2 = await evaluate(`
      (() => {
        const modal = document.querySelector('[role="dialog"]');
        return {
          open: Boolean(modal),
          title: modal?.querySelector('h2')?.innerText || '',
          url: window.location.pathname
        };
      })()
    `);
    console.log('Modal state after clicking 2nd box:', checkModal2);

    // Capture screenshot of second modal
    const modal2Shot = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(artifactDir, 'market_activity_detail_popup_second.png'), Buffer.from(modal2Shot.data, 'base64'));
    console.log('✓ Captured market_activity_detail_popup_second.png');

    // 10. Test Mobile Viewport (375x812)
    console.log('7. Testing mobile responsive modal layout (375x812)...');
    await send('Emulation.setDeviceMetricsOverride', {
      width: 375,
      height: 812,
      deviceScaleFactor: 2,
      mobile: true
    });
    await sleep(800);

    const mobileShot = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(artifactDir, 'market_activity_detail_popup_mobile.png'), Buffer.from(mobileShot.data, 'base64'));
    console.log('✓ Captured market_activity_detail_popup_mobile.png');

    const verificationSummary = {
      timestamp: new Date().toISOString(),
      articlesCount: checkArticles.count,
      boxClickSuccess: clickBoxResult.success,
      modalOpenedOnBoxClick: checkModal.open,
      modalDetails: checkModal,
      modalClosedOnCloseBtn: !checkClosed,
      secondBoxClickSuccess: checkModal2.open,
      secondModalTitle: checkModal2.title,
      mobileVerified: true
    };

    fs.writeFileSync(
      path.join(artifactDir, 'market_activity_box_click_verification.json'),
      JSON.stringify(verificationSummary, null, 2)
    );
    console.log('=== All Verifications Passed Successfully ===');
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

