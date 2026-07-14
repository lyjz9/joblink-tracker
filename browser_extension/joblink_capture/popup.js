const captureButton = document.querySelector('#captureButton');
const statusBox = document.querySelector('#status');

function setStatus(message, type = '') {
  statusBox.textContent = message;
  statusBox.className = type;
}

async function currentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab && tab.id && /^https?:\/\//i.test(tab.url || '')) {
    return tab;
  }

  const openTabs = await chrome.tabs.query({ currentWindow: true });
  const jobTab = openTabs.find((item) => (
    item.id &&
    /^https?:\/\//i.test(item.url || '') &&
    /\b(linkedin|indeed|glassdoor|monster|wellfound|upwork|ziprecruiter|greenhouse|lever|ashby|workdayjobs|icims|breezy|smartrecruiters|careers?|jobs?)\b/i.test(item.url || '')
  ));
  if (jobTab) {
    await chrome.tabs.update(jobTab.id, { active: true });
    return jobTab;
  }

  const current = tab && tab.url ? ` Current tab is ${tab.url}.` : '';
  throw new Error(`Open the actual job posting, then try JobLink Capture again.${current}`);
}

async function readFullJobPage() {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const originalX = window.scrollX;
  const originalY = window.scrollY;
  const snapshots = [];
  const seen = new Set();

  function cleanText(value) {
    return String(value || '').replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  }

  function pageText() {
    return cleanText(
      (document.body && document.body.innerText) ||
      (document.documentElement && document.documentElement.innerText) ||
      (document.body && document.body.textContent) ||
      (document.documentElement && document.documentElement.textContent) ||
      '',
    );
  }

  function addSnapshot(label) {
    const text = pageText();
    if (!text || seen.has(text)) return;
    seen.add(text);
    snapshots.push({ label, text: text.slice(0, 120000) });
  }

  function clickExpanders() {
    const expanderPattern = /\b(show|see|read|view|load)\s+(more|full|details|description|job)|more\s+details|expand\b/i;
    const controls = Array.from(document.querySelectorAll('button, a, [role="button"]'));
    let clicked = 0;
    for (const control of controls) {
      const label = cleanText(control.innerText || control.textContent || control.getAttribute('aria-label') || '');
      const rect = control.getBoundingClientRect();
      if (!label || label.length > 80 || !expanderPattern.test(label)) continue;
      if (rect.width <= 0 || rect.height <= 0) continue;
      try {
        control.click();
        clicked += 1;
      } catch (error) {
        // Ignore controls that the page refuses to click.
      }
      if (clicked >= 8) break;
    }
    return clicked;
  }

  function readMeta() {
    const meta = {};
    for (const tag of document.querySelectorAll('meta[name], meta[property]')) {
      const key = tag.getAttribute('property') || tag.getAttribute('name');
      const value = tag.getAttribute('content');
      if (key && value && value.length < 5000) meta[key] = value;
    }
    return meta;
  }

  function visibleText(element) {
    const rect = element.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return '';
    return cleanText(element.innerText || element.textContent || '');
  }

  function uniqueShort(values, limit = 40) {
    const result = [];
    const keys = new Set();
    for (const value of values) {
      const text = cleanText(value);
      const key = text.toLowerCase();
      if (!text || keys.has(key) || text.length > 220) continue;
      keys.add(key);
      result.push(text);
      if (result.length >= limit) break;
    }
    return result;
  }

  function readFieldCandidates() {
    const headings = uniqueShort(
      Array.from(document.querySelectorAll('h1, h2, [role="heading"]'))
        .map((element) => visibleText(element)),
      30,
    );

    const fieldLabels = /(company|client|employer|organization|location|job location|workplace|work type|job type|salary|compensation|pay range|base pay|budget|hourly|fixed-price|fixed price|rate|remote job)/i;
    const labelPairs = [];
    const possibleLabels = Array.from(document.querySelectorAll('dt, th, strong, b, span, div, li'))
      .filter((element) => {
        const text = visibleText(element);
        return text && text.length <= 70 && fieldLabels.test(text);
      })
      .slice(0, 180);

    for (const element of possibleLabels) {
      const label = visibleText(element);
      const row = element.closest('li, tr, dl, div, section, article');
      const rowText = row ? visibleText(row) : '';
      const next = element.nextElementSibling ? visibleText(element.nextElementSibling) : '';
      const parent = element.parentElement ? visibleText(element.parentElement) : '';
      for (const value of [next, rowText, parent]) {
        if (value && value !== label && value.length <= 500) {
          labelPairs.push({ label, value });
          break;
        }
      }
    }

    const headerSelectors = [
      'main',
      'article',
      '[class*="job" i]',
      '[class*="posting" i]',
      '[class*="career" i]',
      '[class*="opening" i]',
      '[data-testid*="job" i]',
      '[data-qa*="job" i]',
    ];
    const headerBlocks = uniqueShort(
      Array.from(document.querySelectorAll(headerSelectors.join(',')))
        .map((element) => visibleText(element).split('\n').slice(0, 24).join('\n')),
      35,
    );

    const keywordLines = [];
    const keywordPattern = /\b(remote|remote job|hybrid|on-site|onsite|in-office|salary|compensation|base pay|budget|hourly|fixed-price|fixed price|rate|equity|stock options|\$[\d,]+|location|client|new york|new jersey|california|texas|united states|worldwide)\b/i;
    for (const line of pageText().split('\n')) {
      if (keywordPattern.test(line) && line.length <= 220) keywordLines.push(line);
      if (keywordLines.length >= 80) break;
    }

    return {
      headings,
      labelPairs,
      headerBlocks,
      keywordLines: uniqueShort(keywordLines, 80),
    };
  }

  const jsonld = Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
    .map((script) => script.textContent || '')
    .filter(Boolean)
    .slice(0, 20);
  const nextData = document.querySelector('script#__NEXT_DATA__')?.textContent || '';
  const jsonScripts = Array.from(document.querySelectorAll('script[type="application/json"], script:not([src])'))
    .map((script) => script.textContent || '')
    .filter((text) => /\b(job|posting|client|company|budget|hourly|salary|compensation|location|remote)\b/i.test(text))
    .slice(0, 12)
    .map((text) => text.slice(0, 100000));

  clickExpanders();
  await sleep(300);
  addSnapshot('top');

  let lastHeight = 0;
  let sameHeightCount = 0;
  for (let pass = 0; pass < 70; pass += 1) {
    const pageHeight = Math.max(
      document.documentElement.scrollHeight,
      document.body ? document.body.scrollHeight : 0,
    );
    const step = Math.max(420, Math.floor(window.innerHeight * 0.75));
    const y = Math.min(pass * step, Math.max(0, pageHeight - window.innerHeight));
    window.scrollTo(0, y);
    await sleep(180);
    clickExpanders();
    addSnapshot(`scroll-${pass}`);

    if (y >= pageHeight - window.innerHeight - 4) {
      if (pageHeight === lastHeight) sameHeightCount += 1;
      if (sameHeightCount >= 2) break;
      lastHeight = pageHeight;
    }
  }

  window.scrollTo(originalX, originalY);
  await sleep(50);

  return {
    url: location.href,
    title: document.title,
    text: snapshots.map((item) => item.text).join('\n\n').slice(0, 600000),
    snapshots,
    candidates: readFieldCandidates(),
    meta: readMeta(),
    jsonld,
    next_data: nextData.slice(0, 400000),
    json_scripts: jsonScripts,
    html: document.documentElement.outerHTML.slice(0, 1200000),
    capture_debug: {
      text_length: snapshots.map((item) => item.text).join('\n\n').length,
      html_length: document.documentElement.outerHTML.length,
      snapshot_count: snapshots.length,
    },
  };
}

async function capturePage() {
  captureButton.disabled = true;
  setStatus('Capturing full page...');

  try {
    const tab = await currentTab();
    const [page] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: readFullJobPage,
    });

    const response = await fetch('http://127.0.0.1:5050/api/capture-page', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(page.result),
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.error || 'JobLink could not receive this page.');
    }

    const job = payload.job || {};
    const debug = page.result.capture_debug || {};
    const warning = Number(debug.text_length || 0) < 50
      ? ' Very little page text was visible, so review the result.'
      : '';
    setStatus(`Captured ${job.job_title || 'this job page'}.${warning} Go back to JobLink and choose Load browser captures.`, 'success');
  } catch (error) {
    setStatus(error.message || 'JobLink could not capture this page.', 'error');
  } finally {
    captureButton.disabled = false;
  }
}

captureButton.addEventListener('click', capturePage);
