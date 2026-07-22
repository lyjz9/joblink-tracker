const state = {
  jobs: [],
  processing: false,
  activeJobId: null,
  progressRun: 0,
  workbookFile: null,
  workbookHandle: null,
  filter: 'all',
};

const STORAGE_KEY = 'joblink.beta.session.v1';
const FILTERS = ['all', 'ready', 'review', 'error', 'manual'];

const elements = {
  links: document.querySelector('#jobLinks'),
  appliedDate: document.querySelector('#appliedDate'),
  counter: document.querySelector('#linkCounter'),
  validation: document.querySelector('#validationMessage'),
  extract: document.querySelector('#extractButton'),
  clear: document.querySelector('#clearButton'),
  clearResults: document.querySelector('#clearResultsButton'),
  reportSelected: document.querySelector('#reportSelectedButton'),
  selectionCount: document.querySelector('#selectionCount'),
  selectAll: document.querySelector('#selectAllRows'),
  selectAllButton: document.querySelector('#selectAllButton'),
  manualAdd: document.querySelector('#manualAddButton'),
  manualPanel: document.querySelector('#manualPanel'),
  manualCancel: document.querySelector('#manualCancelButton'),
  manualValidation: document.querySelector('#manualValidation'),
  manualCompany: document.querySelector('#manualCompany'),
  manualTitle: document.querySelector('#manualTitle'),
  manualLocation: document.querySelector('#manualLocation'),
  manualWorkType: document.querySelector('#manualWorkType'),
  manualSalary: document.querySelector('#manualSalary'),
  manualSource: document.querySelector('#manualSource'),
  manualLink: document.querySelector('#manualLink'),
  download: document.querySelector('#downloadButton'),
  chooseWorkbook: document.querySelector('#chooseWorkbookButton'),
  workbookFile: document.querySelector('#workbookFile'),
  workbookName: document.querySelector('#workbookName'),
  duplicateMode: document.querySelector('#duplicateMode'),
  appendWorkbook: document.querySelector('#appendWorkbookButton'),
  retryAll: document.querySelector('#retryAllButton'),
  loadCaptures: document.querySelector('#loadCapturesButton'),
  progress: document.querySelector('#progress'),
  progressBar: document.querySelector('#progressBar'),
  progressText: document.querySelector('#progressText'),
  cancelJob: document.querySelector('#cancelJobButton'),
  body: document.querySelector('#resultsBody'),
  table: document.querySelector('#tableWrap'),
  empty: document.querySelector('#emptyState'),
  total: document.querySelector('#totalCount'),
  ready: document.querySelector('#readyCount'),
  review: document.querySelector('#reviewCount'),
  error: document.querySelector('#errorCount'),
  manual: document.querySelector('#manualCount'),
  emptyTitle: document.querySelector('#emptyTitle'),
  toast: document.querySelector('#toast'),
  health: document.querySelector('#healthStatus'),
  feedbackButton: document.querySelector('#feedbackButton'),
  feedbackPanel: document.querySelector('#feedbackPanel'),
  feedbackForm: document.querySelector('#feedbackForm'),
  feedbackType: document.querySelector('#feedbackType'),
  feedbackMessage: document.querySelector('#feedbackMessage'),
  feedbackValidation: document.querySelector('#feedbackValidation'),
  feedbackClose: document.querySelector('#feedbackCloseButton'),
  feedbackCancel: document.querySelector('#feedbackCancelButton'),
  filterTabs: Array.from(document.querySelectorAll('.filter-tab')),
};

function icon(name) {
  return `<i data-lucide="${name}" aria-hidden="true"></i>`;
}

function refreshIcons() {
  if (window.lucide) window.lucide.createIcons();
}

function todayIso() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function selectedAppliedDate() {
  const value = elements.appliedDate.value;
  if (!value) return '';
  const [year, month, day] = value.split('-');
  return `${month}/${day}/${year}`;
}

function missingValue(value) {
  return !value || ['n/a', 'none', 'null'].includes(String(value).trim().toLowerCase());
}

function looksSuspicious(job) {
  const company = String(job.company || '').trim().toLowerCase();
  const location = String(job.location || '').trim().toLowerCase();
  const workType = String(job.work_type || '').trim().toLowerCase();
  if (['remote', 'hybrid', 'onsite', 'on-site'].includes(location)) return true;
  if (['early career', 'careers', 'jobs', 'talent', 'recruiting'].includes(company)) return true;
  if (company.length > 55 || /(this position|company reserves|benefit programs|base salary|apply now|select how often)/i.test(company)) return true;
  if (String(job.location || '').length > 70 || /(posted|time type|apply|salary|experience|job segment|view all jobs)/i.test(location)) return true;
  return workType === 'mix';
}

function urlsFromInput() {
  const seen = new Set();
  const matches = elements.links.value.match(/https?:\/\/[^\s<>"']+/gi) || [];
  return matches
    .map((value) => value.replace(/[.,;:!\)\]\}]+$/, ''))
    .filter((value) => {
      const key = linkKey(value);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function validateInput() {
  const urls = urlsFromInput();
  const hasTextWithoutUrl = elements.links.value.trim() && !urls.length;
  elements.counter.textContent = `${urls.length} / 20`;
  elements.validation.textContent = hasTextWithoutUrl
    ? 'I could not find a complete web address.'
    : urls.length > 20
      ? 'Process up to 20 links at a time.'
      : '';
  elements.extract.disabled = state.processing || !urls.length || urls.length > 20;
  elements.clear.disabled = state.processing || !elements.links.value;
  return urls;
}

function jobStatus(job) {
  if (job.error) return 'error';
  if (isManualJob(job) && !missingRequiredFields(job).length) return 'ready';
  if ((job.review_issues && job.review_issues.length) || job.review_notes) return 'review';
  const required = ['company', 'job_title', 'location'];
  return required.some((key) => missingValue(job[key])) || looksSuspicious(job) ? 'review' : 'ready';
}

function missingRequiredFields(job) {
  return ['company', 'job_title', 'location'].filter((key) => missingValue(job[key]));
}

function isManualJob(job) {
  return String(job.confidence || '').trim().toLowerCase() === 'manual' || job.manual === true;
}

function matchesFilter(job) {
  if (state.filter === 'manual') return isManualJob(job);
  if (state.filter === 'all') return true;
  return jobStatus(job) === state.filter;
}

function visibleJobs() {
  return state.jobs
    .map((job, index) => ({ job, index }))
    .filter(({ job }) => matchesFilter(job));
}

function linkKey(value) {
  return String(value || '').trim().replace(/\/+$/, '').toLowerCase();
}

function findJobIndexByLink(url) {
  const key = linkKey(url);
  if (!key) return -1;
  return state.jobs.findIndex((job) => linkKey(job.job_link) === key);
}

function duplicateResultChoice(url) {
  const existingIndex = findJobIndexByLink(url);
  if (existingIndex < 0) return { action: 'add', index: -1 };
  const action = elements.duplicateMode?.value === 'update' ? 'update' : 'skip';
  return { action, index: existingIndex };
}

function saveSession() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      jobs: state.jobs.map(({ selected, ...job }) => job),
      filter: state.filter,
      links: elements.links.value,
      appliedDate: elements.appliedDate.value,
      duplicateMode: elements.duplicateMode?.value || 'skip',
    }));
  } catch (error) {
    // Browser storage can be disabled; the app still works without persistence.
  }
}

function restoreSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw);
    if (Array.isArray(saved.jobs)) {
      state.jobs = saved.jobs.map((job) => ({ ...job, selected: false }));
    }
    if (FILTERS.includes(saved.filter)) state.filter = saved.filter;
    if (typeof saved.links === 'string') elements.links.value = saved.links;
    if (typeof saved.appliedDate === 'string' && saved.appliedDate) elements.appliedDate.value = saved.appliedDate;
    if (saved.duplicateMode && elements.duplicateMode) elements.duplicateMode.value = saved.duplicateMode;
  } catch (error) {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function badge(status) {
  const labels = { ready: 'Ready', review: 'Review', error: 'Error' };
  return `<span class="badge badge-${status}">${labels[status]}</span>`;
}

function confidenceBadge(job) {
  const level = String(job.confidence || '').toLowerCase();
  if (!level) return '';
  const score = Number.isFinite(Number(job.confidence_score)) ? ` ${Number(job.confidence_score)}` : '';
  return `<span class="confidence confidence-${level}">${escapeHtml(job.confidence)}${score}</span>`;
}

function reviewDetails(job) {
  if (Array.isArray(job.review_details) && job.review_details.length) return job.review_details;
  const fallback = {
    missing_company: ['Company missing', 'Open the posting and fill in the employer name.'],
    missing_job_title: ['Job title missing', 'Open the posting and fill in the role title.'],
    missing_location: ['Location missing', 'Fill in the location if the posting shows one.'],
    generic_company: ['Company too generic', 'Replace the job-board name with the real employer.'],
    generic_job_title: ['Title too generic', 'Replace blocked-page text with the real role title.'],
    scrape_error: ['Scrape failed', 'Retry, use capture, or edit the fields and click the check.'],
  };
  return (job.review_issues || []).map((issue) => ({
    code: issue,
    label: fallback[issue]?.[0] || issue.replaceAll('_', ' '),
    action: fallback[issue]?.[1] || 'Review this row.',
  }));
}

function reviewList(job) {
  const details = reviewDetails(job).slice(0, 4);
  if (!details.length) return '';
  return `<ul class="issue-list">${details.map((item) => (
    `<li><b>${escapeHtml(item.label)}</b><span>${escapeHtml(item.action || '')}</span></li>`
  )).join('')}</ul>`;
}

function fieldOptions(job, key) {
  const values = (job.field_options && Array.isArray(job.field_options[key])) ? job.field_options[key] : [];
  const current = String(job[key] || '').trim().toLowerCase();
  const options = values
    .filter((value) => value && String(value).trim().toLowerCase() !== current)
    .slice(0, 3);
  if (!options.length) return '';
  return `<div class="option-chips">${options.map((value) => (
    `<button class="option-chip" type="button" data-key="${key}" data-value="${escapeHtml(value)}">${escapeHtml(value)}</button>`
  )).join('')}</div>`;
}

function editableCell(job, key) {
  const value = job[key] || 'n/a';
  const muted = String(value).toLowerCase() === 'n/a' ? ' muted-value' : '';
  return `<div class="editable${muted}" contenteditable="true" data-key="${key}" spellcheck="false">${escapeHtml(value)}</div>${fieldOptions(job, key)}`;
}

function reliabilityBadge(job) {
  const level = String(job.source_reliability_label || job.source_reliability?.level || '').toLowerCase();
  if (!level) return '';
  const label = job.source_reliability_label || job.source_reliability.level;
  return `<span class="reliability reliability-${level}">${escapeHtml(label)}</span>`;
}

function sourceCell(job) {
  const note = job.source_reliability_note || job.source_reliability?.note || '';
  const preferred = job.preferred_job_link || '';
  return `
    <div class="source-cell">
      <span>${escapeHtml(job.source || 'n/a')}</span>
      ${reliabilityBadge(job)}
      ${note ? `<small>${escapeHtml(note)}</small>` : ''}
      ${preferred ? `<a href="${escapeHtml(preferred)}" target="_blank" rel="noopener noreferrer">Employer link</a>` : ''}
    </div>`;
}

function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = String(value ?? '');
  return div.innerHTML;
}

function render() {
  const rows = visibleJobs();
  const selectedCount = state.jobs.filter((job) => job.selected).length;
  const selectedVisibleCount = rows.filter(({ job }) => job.selected).length;
  const allSelected = Boolean(rows.length) && selectedVisibleCount === rows.length;
  const someSelected = selectedCount > 0;

  elements.body.innerHTML = rows.map(({ job, index }) => {
    const status = jobStatus(job);
    const detail = job.error || job.review_notes || '';
    const canUseEdited = status === 'error' || status === 'review';
    return `
      <tr data-index="${index}">
        <td class="select-cell">
          <input class="select-row" type="checkbox" aria-label="Select result row" ${job.selected ? 'checked' : ''}>
        </td>
        <td>
          <div class="status-stack">
            <div class="status-row">${badge(status)}${confidenceBadge(job)}</div>
            ${detail ? `<span class="${status === 'error' ? 'error-detail' : 'review-detail'}">${escapeHtml(detail)}</span>` : ''}
            ${reviewList(job)}
          </div>
        </td>
        <td>${editableCell(job, 'company')}</td>
        <td>${editableCell(job, 'job_title')}</td>
        <td>${editableCell(job, 'location')}</td>
        <td>${editableCell(job, 'work_type')}</td>
        <td>${editableCell(job, 'salary')}</td>
        <td>${sourceCell(job)}</td>
        <td>
          <div class="row-actions">
            <button class="icon-button retry-row" type="button" title="Retry extraction" aria-label="Retry extraction">${icon('rotate-cw')}</button>
            ${canUseEdited ? `<button class="icon-button use-row" type="button" title="Use edited row" aria-label="Use edited row">${icon('check-circle')}</button>` : ''}
            <button class="icon-button report-row" type="button" title="Flag this row" aria-label="Flag this row">${icon('flag')}</button>
            <a class="icon-button" href="${escapeHtml(job.job_link || '#')}" target="_blank" rel="noopener noreferrer" title="Open job posting" aria-label="Open job posting">${icon('external-link')}</a>
            <button class="icon-button remove-row" type="button" title="Remove row" aria-label="Remove row">${icon('x')}</button>
          </div>
        </td>
      </tr>`;
  }).join('');

  const counts = state.jobs.reduce((result, job) => {
    result[jobStatus(job)] += 1;
    if (isManualJob(job)) result.manual += 1;
    return result;
  }, { ready: 0, review: 0, error: 0, manual: 0 });
  elements.total.textContent = state.jobs.length;
  elements.ready.textContent = counts.ready;
  elements.review.textContent = counts.review;
  elements.error.textContent = counts.error;
  if (elements.manual) elements.manual.textContent = counts.manual;
  elements.table.hidden = !rows.length;
  elements.empty.hidden = Boolean(rows.length);
  if (elements.emptyTitle) {
    elements.emptyTitle.textContent = state.jobs.length
      ? 'No jobs in this view'
      : 'No jobs yet';
  }
  const hasExportableJobs = state.jobs.some((job) => !job.error);
  elements.download.disabled = !hasExportableJobs;
  elements.appendWorkbook.disabled = state.processing || !hasExportableJobs || !state.workbookFile;
  elements.retryAll.disabled = state.processing || !state.jobs.some((job) => jobStatus(job) !== 'ready');
  elements.appliedDate.disabled = state.processing;
  elements.clearResults.disabled = state.processing || !someSelected;
  if (elements.reportSelected) elements.reportSelected.disabled = state.processing || !someSelected;
  elements.clearResults.innerHTML = `${icon('trash-2')} Remove selected${selectedCount ? ` (${selectedCount})` : ''}`;
  if (elements.selectionCount) {
    elements.selectionCount.textContent = `${selectedCount} selected`;
  }
  if (elements.selectAll) {
    elements.selectAll.checked = allSelected;
    elements.selectAll.indeterminate = selectedVisibleCount > 0 && !allSelected;
    elements.selectAll.disabled = state.processing || !rows.length;
  }
  if (elements.selectAllButton) {
    elements.selectAllButton.disabled = state.processing || !rows.length;
    elements.selectAllButton.innerHTML = `${icon(allSelected ? 'square' : 'check-square')} ${allSelected ? 'Deselect all' : 'Select all'}`;
  }
  elements.filterTabs.forEach((tab) => {
    const active = tab.dataset.filter === state.filter;
    tab.classList.toggle('is-active', active);
    tab.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
  validateInput();
  refreshIcons();
  saveSession();
}

async function scrapeOne(url) {
  const response = await fetch('/scrape', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  const result = await response.json().catch(() => ({ error: 'JobLink received a response it could not read.' }));
  if (!response.ok && !result.error) result.error = `JobLink could not finish that request (${response.status}).`;
  return { ...result, job_link: result.job_link || url, date_applied: selectedAppliedDate() || result.date_applied };
}

function wait(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function createScrapeJob(urls, dateApplied) {
  const response = await fetch('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ urls, date_applied: dateApplied }),
  });
  const payload = await response.json().catch(() => ({ error: 'JobLink received a response it could not read.' }));
  if (!response.ok) throw new Error(payload.error || `JobLink could not finish that request (${response.status}).`);
  return payload;
}

async function readScrapeJob(pollUrl) {
  const response = await fetch(pollUrl, { cache: 'no-store' });
  const payload = await response.json().catch(() => ({ error: 'JobLink received a response it could not read.' }));
  if (!response.ok) throw new Error(payload.error || `JobLink could not finish that request (${response.status}).`);
  return payload;
}

function applyScrapeSnapshot(snapshot, plan, appliedItems, dateApplied) {
  let changed = false;
  (snapshot.items || []).forEach((item, index) => {
    if (!['completed', 'failed'].includes(item.status) || appliedItems.has(index)) return;
    const target = plan[index];
    if (!target) return;
    const result = {
      ...(item.result || { error: 'JobLink could not read this job page.' }),
      job_link: item.result?.job_link || target.url,
    };
    if (dateApplied) result.date_applied = dateApplied;
    if (target.action === 'update') {
      result.selected = Boolean(state.jobs[target.index]?.selected);
      state.jobs[target.index] = result;
    } else {
      result.selected = false;
      state.jobs.push(result);
    }
    appliedItems.add(index);
    changed = true;
  });
  return changed;
}

async function processLinks() {
  const urls = validateInput();
  if (!urls.length || state.processing) return;
  const plan = [];
  let skipped = 0;
  urls.forEach((url) => {
    const duplicate = duplicateResultChoice(url);
    if (duplicate.action === 'skip') {
      skipped += 1;
    } else {
      plan.push({ url, ...duplicate });
    }
  });
  if (!plan.length) {
    showToast(skipped === 1 ? 'That link is already here' : `${skipped} links are already here`);
    return;
  }

  const runId = state.progressRun + 1;
  state.progressRun = runId;
  state.processing = true;
  elements.progress.hidden = false;
  elements.progressBar.style.width = '0%';
  elements.progressText.textContent = 'Starting';
  elements.cancelJob.hidden = true;
  elements.cancelJob.disabled = false;
  render();

  const appliedItems = new Set();
  const dateApplied = selectedAppliedDate();
  let finalStatus = 'stopped';
  try {
    let snapshot = await createScrapeJob(plan.map(({ url }) => url), dateApplied);
    state.activeJobId = snapshot.job_id;
    elements.cancelJob.hidden = false;
    while (true) {
      const changed = applyScrapeSnapshot(snapshot, plan, appliedItems, dateApplied);
      const settled = (snapshot.items || []).filter((item) => !['queued', 'running'].includes(item.status)).length;
      const processed = skipped + settled;
      elements.progressBar.style.width = `${Math.round((processed / urls.length) * 100)}%`;
      elements.progressText.textContent = `${processed} of ${urls.length}`;
      if (changed) render();
      if (['completed', 'cancelled'].includes(snapshot.status)) {
        finalStatus = snapshot.status;
        break;
      }
      await wait(600);
      snapshot = await readScrapeJob(snapshot.poll_url || `/api/jobs/${snapshot.job_id}`);
    }
    if (finalStatus === 'completed') {
      showToast(`Finished ${appliedItems.size} ${appliedItems.size === 1 ? 'job' : 'jobs'}${skipped ? `; ${skipped} already existed` : ''}`);
    } else {
      showToast(`Finished ${appliedItems.size} before you cancelled`);
    }
  } catch (error) {
    elements.progressText.textContent = 'Stopped';
    showToast(error.message || 'Something stopped the scrape. Try those links again.');
  } finally {
    state.activeJobId = null;
    state.processing = false;
    elements.cancelJob.hidden = true;
    elements.progressText.textContent = finalStatus === 'completed' ? 'Complete' : finalStatus === 'cancelled' ? 'Cancelled' : 'Stopped';
    render();
    validateInput();
    window.setTimeout(() => {
      if (state.progressRun === runId && !state.processing) elements.progress.hidden = true;
    }, 1200);
  }
}

async function cancelActiveJob() {
  const jobId = state.activeJobId;
  if (!jobId || elements.cancelJob.disabled) return;
  elements.cancelJob.disabled = true;
  elements.progressText.textContent = 'Stopping';
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || 'JobLink could not stop this batch.');
  } catch (error) {
    showToast(error.message);
    if (state.activeJobId === jobId) elements.cancelJob.disabled = false;
  }
}

async function retryJob(index) {
  const current = state.jobs[index];
  if (!current || !current.job_link || state.processing) return;
  state.processing = true;
  render();
  const retried = await scrapeOne(current.job_link);
  state.jobs[index] = retried;
  state.processing = false;
  render();
  showToast(jobStatus(retried) === 'ready' ? 'Job updated' : 'This job still needs a look');
}

async function retryAllErrors() {
  if (state.processing) return;
  const indexes = state.jobs.map((job, index) => jobStatus(job) !== 'ready' ? index : -1).filter((index) => index >= 0);
  if (!indexes.length) return;
  state.processing = true;
  render();
  for (const index of indexes) {
    state.jobs[index] = await scrapeOne(state.jobs[index].job_link);
  }
  state.processing = false;
  render();
  const remaining = state.jobs.filter((job) => jobStatus(job) !== 'ready').length;
  showToast(remaining ? `${remaining} ${remaining === 1 ? 'row still needs' : 'rows still need'} a look` : 'Everything is ready now');
}

async function reportJob(index) {
  const job = state.jobs[index];
  if (!job) return;
  try {
    const response = await fetch('/api/report-issue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job, status: jobStatus(job) }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || 'JobLink could not save this row for review.');
    showToast('Saved this row for review');
  } catch (error) {
    showToast(error.message);
  }
}

async function reportSelectedJobs() {
  const selected = state.jobs
    .map((job, index) => ({ job, index }))
    .filter(({ job }) => job.selected);
  if (!selected.length || state.processing) return;
  state.processing = true;
  render();
  let saved = 0;
  let failed = 0;
  for (const { job } of selected) {
    try {
      const response = await fetch('/api/report-issue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job, status: jobStatus(job), note: 'Reported from selected rows' }),
      });
      if (response.ok) {
        saved += 1;
      } else {
        failed += 1;
      }
    } catch (error) {
      failed += 1;
    }
  }
  state.processing = false;
  render();
  showToast(failed ? `${saved} saved; ${failed} could not be saved` : `${saved} ${saved === 1 ? 'row' : 'rows'} saved for review`);
}

async function loadCaptures() {
  if (state.processing) return;
  try {
    const response = await fetch('/api/captures');
    if (!response.ok) throw new Error('JobLink could not load your browser captures.');
    const payload = await response.json();
    const captures = Array.isArray(payload.jobs) ? payload.jobs : [];
    let added = 0;
    let updated = 0;
    const appliedDate = selectedAppliedDate();

    captures.slice().reverse().forEach((job) => {
      const incoming = { ...job, date_applied: appliedDate || job.date_applied };
      delete incoming.selected;
      const url = String(incoming.job_link || '').trim();
      if (!url) return;
      const duplicate = duplicateResultChoice(url);
      if (duplicate.action === 'skip') return;
      if (duplicate.action === 'update') {
        state.jobs[duplicate.index] = incoming;
        updated += 1;
      } else {
        state.jobs.push(incoming);
        added += 1;
      }
    });

    render();
    if (added || updated) {
      showToast(`${added} added${updated ? ` and ${updated} updated` : ''}`);
    } else {
      showToast(captures.length ? 'Those browser captures are already here' : 'No browser captures yet');
    }
  } catch (error) {
    showToast(error.message);
  }
}

async function downloadExcel() {
  const jobs = exportableJobs();
  if (!jobs.length) return;
  elements.download.disabled = true;
  try {
    const response = await fetch('/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(jobs),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.error || 'JobLink could not create the Excel file.');
    }
    await downloadResponse(response, 'job_tracker_export.xlsx');
    showToast('Your Excel file is ready');
  } catch (error) {
    showToast(error.message);
  } finally {
    elements.download.disabled = false;
  }
}

async function postWorkbookUpdate(jobs) {
  const workbookFile = await currentWorkbookFile();
  if (!workbookFile) return null;
  const formData = new FormData();
  formData.append('workbook', workbookFile);
  formData.append('jobs', JSON.stringify(jobs));
  formData.append('duplicate_mode', elements.duplicateMode?.value || 'skip');
  return fetch('/append-workbook', {
    method: 'POST',
    body: formData,
  });
}

async function appendToWorkbook() {
  const jobs = exportableJobs();
  const workbookFile = await currentWorkbookFile();
  if (!jobs.length || !workbookFile) return;
  elements.appendWorkbook.disabled = true;
  try {
    let response;
    try {
      response = await postWorkbookUpdate(jobs);
    } catch (error) {
      response = await postWorkbookUpdate(jobs);
    }
    if (!response) throw new Error('Choose an Excel tracker to update.');
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.error || 'JobLink could not update this tracker.');
    }
    const blob = await response.blob();
    const added = response.headers.get('X-JobLink-Added') || '0';
    const skipped = response.headers.get('X-JobLink-Skipped') || '0';
    const updated = response.headers.get('X-JobLink-Updated') || '0';
    const outputName = filenameFromDisposition(response.headers.get('Content-Disposition')) || updatedWorkbookName(workbookFile.name);
    const savedToSelected = await saveBlobToSelectedWorkbook(blob);
    if (!savedToSelected) {
      downloadBlob(blob, outputName);
      state.workbookHandle = null;
      state.workbookFile = new File([blob], outputName, { type: blob.type || workbookFile.type });
      elements.workbookFile.value = '';
      elements.workbookName.textContent = `${outputName} is ready`;
    }
    showToast(`${added} added${Number(updated) ? `, ${updated} updated` : ''}${Number(skipped) ? `, ${skipped} left unchanged` : ''}${savedToSelected ? ' in your tracker' : ''}`);
  } catch (error) {
    showToast(error.message === 'Failed to fetch' ? 'The connection dropped. Choose Update tracker again.' : error.message);
  } finally {
    elements.appendWorkbook.disabled = false;
    render();
  }
}

function exportableJobs() {
  const appliedDate = selectedAppliedDate();
  return state.jobs
    .filter((job) => !job.error)
    .map((job) => {
      const { selected, ...cleanJob } = job;
      return { ...cleanJob, date_applied: appliedDate || cleanJob.date_applied };
    });
}

async function downloadResponse(response, fallbackName) {
  const blob = await response.blob();
  downloadBlob(blob, filenameFromDisposition(response.headers.get('Content-Disposition')) || fallbackName);
}

function downloadBlob(blob, filename) {
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = href;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(href);
}

async function saveBlobToSelectedWorkbook(blob) {
  if (!state.workbookHandle || !state.workbookHandle.createWritable) return false;
  try {
    const writable = await state.workbookHandle.createWritable();
    await writable.write(blob);
    await writable.close();
    state.workbookFile = await state.workbookHandle.getFile();
    elements.workbookName.textContent = `${state.workbookFile.name} is saved`;
    return true;
  } catch (error) {
    showToast('Close the tracker in Excel, then try again.');
    return false;
  }
}

async function chooseWorkbook() {
  if (window.showOpenFilePicker) {
    try {
      const [handle] = await window.showOpenFilePicker({
        multiple: false,
        types: [{
          description: 'Excel workbooks',
          accept: {
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
            'application/vnd.ms-excel.sheet.macroEnabled.12': ['.xlsm'],
          },
        }],
      });
      state.workbookHandle = handle;
      state.workbookFile = await handle.getFile();
      elements.workbookName.textContent = `${state.workbookFile.name} selected`;
      render();
      return;
    } catch (error) {
      if (error.name === 'AbortError') return;
    }
  }
  elements.workbookFile.click();
}

function filenameFromDisposition(header) {
  const encoded = String(header || '').match(/filename\*=UTF-8''([^;]+)/i);
  if (encoded) return decodeURIComponent(encoded[1]);
  const plain = String(header || '').match(/filename="?([^";]+)"?/i);
  return plain ? plain[1] : '';
}

function updatedWorkbookName(filename) {
  const dot = filename.lastIndexOf('.');
  if (dot < 1) return 'job_tracker_with_jobs.xlsx';
  return `${filename.slice(0, dot)}_with_jobs${filename.slice(dot)}`;
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add('is-visible');
  clearTimeout(showToast.timeout);
  showToast.timeout = setTimeout(() => elements.toast.classList.remove('is-visible'), 2600);
}

function toggleFeedbackPanel(show = elements.feedbackPanel.hidden) {
  if (!elements.feedbackPanel) return;
  elements.feedbackPanel.hidden = !show;
  if (show) {
    elements.feedbackValidation.textContent = '';
    elements.feedbackMessage.focus();
  } else {
    elements.feedbackValidation.textContent = '';
  }
}

async function submitFeedback(event) {
  event.preventDefault();
  const message = elements.feedbackMessage.value.trim();
  if (!message) {
    elements.feedbackValidation.textContent = 'Add a short note first.';
    elements.feedbackMessage.focus();
    return;
  }
  const submit = elements.feedbackForm.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    const response = await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: elements.feedbackType.value,
        message,
        page: window.location.href,
        job_count: state.jobs.length,
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || 'JobLink could not save your feedback.');
    elements.feedbackMessage.value = '';
    elements.feedbackType.value = 'general';
    toggleFeedbackPanel(false);
    showToast('Feedback saved on this computer');
  } catch (error) {
    elements.feedbackValidation.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
}

function fieldLabel(key) {
  return {
    company: 'company',
    job_title: 'job title',
    location: 'location',
  }[key] || key;
}

function setAllRowsSelected(selected) {
  visibleJobs().forEach(({ job }) => {
    job.selected = selected;
  });
  render();
}

function useEditedRow(index) {
  const job = state.jobs[index];
  if (!job) return;
  const missing = missingRequiredFields(job);
  if (missing.length) {
    showToast(`Add ${missing.map(fieldLabel).join(', ')} first`);
    return;
  }
  if (missingValue(job.work_type)) job.work_type = 'n/a';
  if (missingValue(job.salary)) job.salary = 'n/a';
  if (missingValue(job.source)) job.source = 'Company Website';
  delete job.error;
  delete job.review_issues;
  delete job.review_notes;
  delete job.review_details;
  job.manual = true;
  job.confidence = 'Manual';
  job.confidence_score = 100;
  render();
  showToast('Your edits are ready for the tracker');
}

async function currentWorkbookFile() {
  if (state.workbookHandle && state.workbookHandle.getFile) {
    state.workbookFile = await state.workbookHandle.getFile();
  } else if (!state.workbookFile && elements.workbookFile.files[0]) {
    state.workbookFile = elements.workbookFile.files[0];
  }
  return state.workbookFile;
}

function toggleManualPanel(show = elements.manualPanel.hidden) {
  elements.manualPanel.hidden = !show;
  if (show) {
    elements.manualValidation.textContent = '';
    if (!elements.manualWorkType.value) elements.manualWorkType.value = 'n/a';
    elements.manualCompany.focus();
  }
}

function resetManualForm() {
  elements.manualPanel.reset();
  elements.manualWorkType.value = 'n/a';
  elements.manualValidation.textContent = '';
}

function manualJobFromForm() {
  return {
    date_applied: selectedAppliedDate(),
    company: elements.manualCompany.value.trim(),
    job_title: elements.manualTitle.value.trim(),
    job_link: elements.manualLink.value.trim(),
    status: 'Applied',
    location: elements.manualLocation.value.trim(),
    work_type: elements.manualWorkType.value || 'n/a',
    salary: elements.manualSalary.value.trim() || 'n/a',
    follow_up: '',
    source: elements.manualSource.value.trim() || 'Company Website',
    confidence: 'Manual',
    confidence_score: 100,
    manual: true,
  };
}

function addManualJob(event) {
  event.preventDefault();
  const job = manualJobFromForm();
  const missing = missingRequiredFields(job);
  if (missing.length) {
    elements.manualValidation.textContent = `Add ${missing.map(fieldLabel).join(', ')} first.`;
    return;
  }
  if (job.job_link && !/^https?:\/\//i.test(job.job_link)) {
    elements.manualValidation.textContent = 'Use a full link that starts with http:// or https://.';
    return;
  }
  if (job.job_link) {
    const duplicate = duplicateResultChoice(job.job_link);
    if (duplicate.action === 'skip') {
      showToast('That link is already here');
      return;
    }
    if (duplicate.action === 'update') {
      state.jobs[duplicate.index] = job;
    } else {
      state.jobs.push(job);
    }
  } else {
    state.jobs.push(job);
  }
  state.filter = 'manual';
  resetManualForm();
  toggleManualPanel(false);
  render();
  showToast('Job added');
}

elements.links.addEventListener('input', () => {
  validateInput();
  saveSession();
});
elements.extract.addEventListener('click', processLinks);
if (elements.cancelJob) elements.cancelJob.addEventListener('click', cancelActiveJob);
elements.download.addEventListener('click', downloadExcel);
elements.appendWorkbook.addEventListener('click', appendToWorkbook);
elements.chooseWorkbook.addEventListener('click', chooseWorkbook);
if (elements.reportSelected) elements.reportSelected.addEventListener('click', reportSelectedJobs);
if (elements.duplicateMode) elements.duplicateMode.addEventListener('change', saveSession);
if (elements.feedbackButton) elements.feedbackButton.addEventListener('click', () => toggleFeedbackPanel());
if (elements.feedbackClose) elements.feedbackClose.addEventListener('click', () => toggleFeedbackPanel(false));
if (elements.feedbackCancel) elements.feedbackCancel.addEventListener('click', () => toggleFeedbackPanel(false));
if (elements.feedbackForm) elements.feedbackForm.addEventListener('submit', submitFeedback);
if (elements.selectAll) elements.selectAll.addEventListener('change', () => setAllRowsSelected(elements.selectAll.checked));
if (elements.selectAllButton) {
  elements.selectAllButton.addEventListener('click', () => {
    const rows = visibleJobs();
    const allSelected = Boolean(rows.length) && rows.every(({ job }) => job.selected);
    setAllRowsSelected(!allSelected);
  });
}
if (elements.manualAdd) elements.manualAdd.addEventListener('click', () => toggleManualPanel());
if (elements.manualCancel) elements.manualCancel.addEventListener('click', () => {
  resetManualForm();
  toggleManualPanel(false);
});
if (elements.manualPanel) elements.manualPanel.addEventListener('submit', addManualJob);
elements.filterTabs.forEach((tab) => {
  tab.addEventListener('click', () => {
    const nextFilter = tab.dataset.filter;
    if (!FILTERS.includes(nextFilter)) return;
    state.filter = nextFilter;
    render();
  });
});
elements.retryAll.addEventListener('click', retryAllErrors);
elements.loadCaptures.addEventListener('click', loadCaptures);
elements.clearResults.addEventListener('click', () => {
  state.jobs = state.jobs.filter((job) => !job.selected);
  render();
});
elements.workbookFile.addEventListener('change', () => {
  const file = elements.workbookFile.files[0] || null;
  state.workbookFile = file;
  state.workbookHandle = null;
  elements.workbookName.textContent = file ? file.name : 'No tracker selected';
  render();
});
elements.clear.addEventListener('click', () => {
  elements.links.value = '';
  render();
});
elements.appliedDate.addEventListener('change', () => {
  const appliedDate = selectedAppliedDate();
  if (appliedDate) state.jobs.forEach((job) => { job.date_applied = appliedDate; });
  render();
});
elements.body.addEventListener('click', (event) => {
  const option = event.target.closest('.option-chip');
  if (option) {
    const row = option.closest('tr');
    const job = state.jobs[Number(row.dataset.index)];
    job[option.dataset.key] = option.dataset.value;
    delete job.review_issues;
    delete job.review_notes;
    delete job.review_details;
    render();
    return;
  }
  const retry = event.target.closest('.retry-row');
  if (retry) {
    retryJob(Number(retry.closest('tr').dataset.index));
    return;
  }
  const useRow = event.target.closest('.use-row');
  if (useRow) {
    useEditedRow(Number(useRow.closest('tr').dataset.index));
    return;
  }
  const report = event.target.closest('.report-row');
  if (report) {
    reportJob(Number(report.closest('tr').dataset.index));
    return;
  }
  const button = event.target.closest('.remove-row');
  if (!button) return;
  const row = button.closest('tr');
  state.jobs.splice(Number(row.dataset.index), 1);
  render();
});
elements.body.addEventListener('change', (event) => {
  const checkbox = event.target.closest('.select-row');
  if (!checkbox) return;
  const row = checkbox.closest('tr');
  state.jobs[Number(row.dataset.index)].selected = checkbox.checked;
  render();
});
elements.body.addEventListener('input', (event) => {
  const editable = event.target.closest('.editable');
  if (!editable) return;
  const row = editable.closest('tr');
  const job = state.jobs[Number(row.dataset.index)];
  job[editable.dataset.key] = editable.textContent.trim();
  delete job.review_issues;
  delete job.review_notes;
  delete job.review_details;
  saveSession();
});

fetch('/health')
  .then((response) => { if (response.ok) elements.health.classList.add('is-online'); })
  .catch(() => {});

elements.appliedDate.value = todayIso();
restoreSession();
render();
