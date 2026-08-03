const state = {
  jobs: [],
  processing: false,
  activeJobId: null,
  progressRun: 0,
  workbookFile: null,
  workbookHandle: null,
  filter: 'all',
  salaryMode: 'original',
  salaryHoursPerWeek: 40,
  view: 'workspace',
  historyEntries: [],
  historyFilter: 'all',
  historyQuery: '',
  historyTotal: 0,
  historyAllCount: 0,
  historyLoaded: false,
  historyLoading: false,
  historyRequest: 0,
  historySaveWarned: false,
  historyError: '',
};

const STORAGE_KEY = 'joblink.beta.session.v1';
const FILTERS = ['all', 'ready', 'review', 'error', 'manual'];
const {
  linkKey,
  mergePastedLinks,
  parseLinksFromText,
} = window.JobLinkInput;
const {
  convertSalary,
  jobWithSalaryDisplay,
  normalizeHoursPerWeek,
  normalizeSalaryMode,
} = window.JobSalaryDisplay;
const linkPasteHistory = [];
const linkPasteRedo = [];
let changingLinksProgrammatically = false;
let historySearchTimer = null;

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
  resultsSummary: document.querySelector('#resultsSummary'),
  resultFilters: document.querySelector('#resultFilters'),
  salaryControls: document.querySelector('#salaryControls'),
  resultsCommandRow: document.querySelector('#resultsCommandRow'),
  selectionActions: document.querySelector('#selectionActions'),
  trackerBar: document.querySelector('#trackerBar'),
  selectAll: document.querySelector('#selectAllRows'),
  selectAllButton: document.querySelector('#selectAllButton'),
  manualAdd: document.querySelector('#manualAddButton'),
  otherAddMenu: document.querySelector('#otherAddMenu'),
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
  trackerSettings: document.querySelector('#trackerSettings'),
  appendWorkbook: document.querySelector('#appendWorkbookButton'),
  appendWorkbookLabel: document.querySelector('#appendWorkbookLabel'),
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
  emptyText: document.querySelector('#emptyText'),
  salaryHoursField: document.querySelector('#salaryHoursField'),
  salaryHoursPerWeek: document.querySelector('#salaryHoursPerWeek'),
  salaryConversionInfo: document.querySelector('#salaryConversionInfo'),
  salaryColumnHeading: document.querySelector('#salaryColumnHeading'),
  salaryModeButtons: Array.from(document.querySelectorAll('.salary-mode-button')),
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
  workspaceView: document.querySelector('#workspaceView'),
  historyView: document.querySelector('#historyView'),
  workspaceViewButton: document.querySelector('#workspaceViewButton'),
  historyViewButton: document.querySelector('#historyViewButton'),
  historyNavCount: document.querySelector('#historyNavCount'),
  historySummary: document.querySelector('#historySummary'),
  historySearch: document.querySelector('#historySearch'),
  historyStatusFilter: document.querySelector('#historyStatusFilter'),
  historyBody: document.querySelector('#historyBody'),
  historyTable: document.querySelector('#historyTableWrap'),
  historyEmpty: document.querySelector('#historyEmptyState'),
  historyEmptyTitle: document.querySelector('#historyEmptyTitle'),
  historyEmptyText: document.querySelector('#historyEmptyText'),
  selectAllHistory: document.querySelector('#selectAllHistory'),
  restoreHistory: document.querySelector('#restoreHistoryButton'),
  exportHistory: document.querySelector('#exportHistoryButton'),
  deleteHistory: document.querySelector('#deleteHistoryButton'),
  clearHistory: document.querySelector('#clearHistoryButton'),
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

function parsedLinksFromInput() {
  return parseLinksFromText(elements.links.value);
}

function urlsFromInput() {
  return parsedLinksFromInput().urls;
}

function validateInput() {
  const { urls, invalidCount } = parsedLinksFromInput();
  const hasTextWithoutUrl = elements.links.value.trim() && !urls.length;
  elements.counter.textContent = `${urls.length} / 20`;
  elements.validation.textContent = invalidCount
    ? `${invalidCount} pasted ${invalidCount === 1 ? 'link looks' : 'links look'} incomplete or malformed.`
    : hasTextWithoutUrl
    ? 'I could not find a complete web address.'
    : urls.length > 20
      ? 'Process up to 20 links at a time.'
      : '';
  elements.extract.disabled = state.processing || !urls.length || urls.length > 20 || invalidCount > 0;
  elements.clear.disabled = state.processing || !elements.links.value;
  return urls;
}

function replaceLinksInput(value) {
  const nextValue = String(value || '');
  elements.links.focus();
  changingLinksProgrammatically = true;
  try {
    if (typeof elements.links.setRangeText === 'function') {
      elements.links.setRangeText(nextValue, 0, elements.links.value.length, 'end');
    } else {
      elements.links.value = nextValue;
    }
  } finally {
    changingLinksProgrammatically = false;
  }
  const end = elements.links.value.length;
  elements.links.setSelectionRange(end, end);
}

function rememberLinksPaste(before, after) {
  if (before === after) return;
  linkPasteHistory.push({ before, after });
  if (linkPasteHistory.length > 50) linkPasteHistory.shift();
  linkPasteRedo.length = 0;
}

function handleLinksHistoryShortcut(event) {
  if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
  const key = String(event.key || '').toLowerCase();
  const undo = key === 'z' && !event.shiftKey;
  const redo = key === 'y' || (key === 'z' && event.shiftKey);
  if (!undo && !redo) return;

  if (undo) {
    const entry = linkPasteHistory[linkPasteHistory.length - 1];
    if (!entry || elements.links.value !== entry.after) return;
    event.preventDefault();
    linkPasteHistory.pop();
    linkPasteRedo.push(entry);
    replaceLinksInput(entry.before);
  } else {
    const entry = linkPasteRedo[linkPasteRedo.length - 1];
    if (!entry || elements.links.value !== entry.before) return;
    event.preventDefault();
    linkPasteRedo.pop();
    linkPasteHistory.push(entry);
    replaceLinksInput(entry.after);
  }
  validateInput();
  saveSession();
}

function handleLinksPaste(event) {
  const clipboardText = event.clipboardData?.getData('text/plain') || '';
  const merged = mergePastedLinks(elements.links.value, clipboardText);
  if (!merged.handled) return;

  event.preventDefault();
  if (merged.addedCount) {
    const before = elements.links.value;
    replaceLinksInput(merged.text);
    rememberLinksPaste(before, elements.links.value);
  } else {
    elements.links.focus();
    const end = elements.links.value.length;
    elements.links.setSelectionRange(end, end);
  }
  validateInput();
  saveSession();

  if (merged.invalidCount) {
    showToast(`${merged.invalidCount} malformed ${merged.invalidCount === 1 ? 'link was' : 'links were'} not added`);
  } else if (!merged.addedCount && merged.duplicateCount) {
    showToast(merged.duplicateCount === 1 ? 'That job link is already listed' : 'Those job links are already listed');
  } else if (merged.duplicateCount) {
    showToast(`${merged.duplicateCount} duplicate ${merged.duplicateCount === 1 ? 'link was' : 'links were'} not added`);
  }
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
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      jobs: state.jobs.map(({ selected, ...job }) => job),
      filter: state.filter,
      links: elements.links.value,
      appliedDate: elements.appliedDate.value,
      duplicateMode: elements.duplicateMode?.value || 'skip',
      salaryMode: state.salaryMode,
      salaryHoursPerWeek: state.salaryHoursPerWeek,
    }));
  } catch (error) {
    // Browser storage can be disabled; the app still works without persistence.
  }
}

function restoreSession() {
  try {
    // Remove workspaces saved by older versions so a newly opened app starts clean.
    localStorage.removeItem(STORAGE_KEY);
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw);
    if (Array.isArray(saved.jobs)) {
      state.jobs = saved.jobs.map((job) => ({ ...job, selected: false }));
    }
    if (FILTERS.includes(saved.filter)) state.filter = saved.filter;
    if (typeof saved.links === 'string') elements.links.value = saved.links;
    if (typeof saved.appliedDate === 'string' && saved.appliedDate) elements.appliedDate.value = saved.appliedDate;
    if (saved.duplicateMode && elements.duplicateMode) elements.duplicateMode.value = saved.duplicateMode;
    state.salaryMode = normalizeSalaryMode(saved.salaryMode);
    state.salaryHoursPerWeek = normalizeHoursPerWeek(saved.salaryHoursPerWeek);
  } catch (error) {
    sessionStorage.removeItem(STORAGE_KEY);
  }
}

function badge(status) {
  const labels = { ready: 'Ready', review: 'Review', error: 'Error', manual: 'Manual' };
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

function salaryCell(job) {
  const original = job.salary || 'n/a';
  if (state.salaryMode === 'original') return editableCell(job, 'salary');

  const converted = convertSalary(
    original,
    state.salaryMode,
    state.salaryHoursPerWeek,
  );
  const classes = ['salary-display-value'];
  if (converted.estimated) classes.push('salary-estimate');
  if (!converted.convertible) classes.push('salary-unconverted');
  if (String(converted.value).toLowerCase() === 'n/a') classes.push('muted-value');

  const tooltip = converted.convertible
    ? converted.estimated
      ? `Estimated from ${original} using ${converted.hoursPerWeek} hours/week and ${converted.weeksPerYear} weeks/year.`
      : `Original: ${original}`
    : `Shown as posted because this salary cannot be converted safely. Original: ${original}`;
  return `<div class="${classes.join(' ')}" title="${escapeHtml(tooltip)}">${escapeHtml(converted.value)}</div>`;
}

function refreshSalaryCells() {
  elements.body.querySelectorAll('tr[data-index]').forEach((row) => {
    const salary = row.querySelector('[data-field="salary"]');
    const job = state.jobs[Number(row.dataset.index)];
    if (salary && job) salary.innerHTML = salaryCell(job);
  });
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
  const hasJobs = state.jobs.length > 0;

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
        <td data-field="salary">${salaryCell(job)}</td>
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
  const hasFlaggedJobs = counts.review + counts.error > 0;
  if (elements.resultsSummary) elements.resultsSummary.hidden = !hasJobs;
  if (elements.resultFilters) elements.resultFilters.hidden = !hasJobs;
  if (elements.salaryControls) elements.salaryControls.hidden = !hasJobs;
  if (elements.resultsCommandRow) elements.resultsCommandRow.hidden = !hasJobs;
  if (elements.selectionActions) elements.selectionActions.hidden = !someSelected;
  if (elements.trackerBar) elements.trackerBar.hidden = !hasJobs;
  elements.table.hidden = !rows.length;
  elements.empty.hidden = Boolean(rows.length);
  if (elements.emptyTitle) {
    elements.emptyTitle.textContent = state.jobs.length
      ? 'No jobs in this view'
      : 'No jobs yet';
  }
  if (elements.emptyText) {
    elements.emptyText.textContent = state.jobs.length
      ? 'Choose another status to see the rest of your results.'
      : 'Paste job links above to get started.';
  }
  const hasExportableJobs = state.jobs.some((job) => !job.error);
  elements.download.disabled = !hasExportableJobs;
  elements.appendWorkbook.disabled = state.processing || !hasExportableJobs || !state.workbookFile;
  if (elements.appendWorkbookLabel) {
    elements.appendWorkbookLabel.textContent = state.workbookFile
      ? (canOverwriteWorkbook() ? 'Update original' : 'Download updated copy')
      : 'Update tracker';
  }
  elements.retryAll.hidden = !hasFlaggedJobs;
  elements.retryAll.disabled = state.processing || !hasFlaggedJobs;
  elements.appliedDate.disabled = state.processing;
  elements.clearResults.disabled = state.processing || !someSelected;
  if (elements.reportSelected) elements.reportSelected.disabled = state.processing || !someSelected;
  elements.clearResults.innerHTML = `${icon('trash-2')} Remove${selectedCount ? ` (${selectedCount})` : ''}`;
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
  elements.salaryModeButtons.forEach((button) => {
    const active = button.dataset.salaryMode === state.salaryMode;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
  if (elements.salaryHoursPerWeek) {
    elements.salaryHoursPerWeek.value = state.salaryHoursPerWeek;
  }
  const showSalaryEstimateSettings = state.salaryMode !== 'original';
  if (elements.salaryHoursField) {
    elements.salaryHoursField.hidden = !showSalaryEstimateSettings;
  }
  if (elements.salaryConversionInfo) {
    elements.salaryConversionInfo.hidden = !showSalaryEstimateSettings;
  }
  if (elements.salaryColumnHeading) {
    elements.salaryColumnHeading.textContent = {
      original: 'Salary',
      hourly: 'Salary (hourly)',
      yearly: 'Salary (yearly)',
    }[state.salaryMode];
  }
  validateInput();
  refreshIcons();
  saveSession();
}

function historyStatusForJob(job) {
  const status = jobStatus(job);
  if (status === 'error' || status === 'review') return status;
  return isManualJob(job) ? 'manual' : 'ready';
}

function formatHistoryDate(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Saved';
  return parsed.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function renderHistory() {
  if (!elements.historyBody) return;
  const entries = state.historyEntries;
  const selectedCount = entries.filter((entry) => entry.selected).length;
  const allSelected = Boolean(entries.length) && selectedCount === entries.length;

  elements.historyBody.innerHTML = entries.map((entry) => {
    const job = entry.job || {};
    const jobLink = String(job.job_link || '');
    const savedDate = formatHistoryDate(entry.updated_at);
    return `
      <tr data-history-id="${entry.id}">
        <td class="select-cell">
          <input class="select-history-row" type="checkbox" aria-label="Select history row" ${entry.selected ? 'checked' : ''}>
        </td>
        <td><span class="history-date" title="${escapeHtml(entry.updated_at || '')}">${escapeHtml(savedDate)}</span></td>
        <td>${badge(entry.status || 'review')}</td>
        <td><div class="history-cell-main"><strong>${escapeHtml(job.company || 'n/a')}</strong></div></td>
        <td><div class="history-cell-main"><strong>${escapeHtml(job.job_title || 'n/a')}</strong></div></td>
        <td><span class="history-date">${escapeHtml(job.date_applied || 'n/a')}</span></td>
        <td>${escapeHtml(job.location || 'n/a')}</td>
        <td>${escapeHtml(job.work_type || 'n/a')}</td>
        <td>${escapeHtml(job.salary || 'n/a')}</td>
        <td><div class="history-cell-main"><strong>${escapeHtml(job.source || 'n/a')}</strong></div></td>
        <td>
          ${jobLink ? `<a class="icon-button" href="${escapeHtml(jobLink)}" target="_blank" rel="noopener noreferrer" title="Open job posting" aria-label="Open job posting">${icon('external-link')}</a>` : ''}
        </td>
      </tr>`;
  }).join('');

  if (state.historyLoading && !state.historyLoaded) {
    elements.historySummary.textContent = 'Loading saved jobs';
  } else if (state.historyTotal === state.historyAllCount) {
    elements.historySummary.textContent = `${state.historyAllCount} saved ${state.historyAllCount === 1 ? 'job' : 'jobs'}`;
  } else {
    elements.historySummary.textContent = `${state.historyTotal} matching · ${state.historyAllCount} saved`;
  }
  if (elements.historyNavCount) elements.historyNavCount.textContent = state.historyAllCount;

  elements.historyTable.hidden = !entries.length;
  elements.historyEmpty.hidden = Boolean(entries.length);
  if (state.historyLoading) {
    elements.historyEmptyTitle.textContent = 'Loading history';
    elements.historyEmptyText.textContent = 'Reading the jobs saved on this computer.';
  } else if (state.historyError) {
    elements.historyEmptyTitle.textContent = 'History could not load';
    elements.historyEmptyText.textContent = state.historyError;
  } else if (state.historyAllCount) {
    elements.historyEmptyTitle.textContent = 'No matching jobs';
    elements.historyEmptyText.textContent = 'Try a different search or status.';
  } else {
    elements.historyEmptyTitle.textContent = 'No saved jobs yet';
    elements.historyEmptyText.textContent = 'Finished scrapes and manual additions will appear here.';
  }

  if (elements.selectAllHistory) {
    elements.selectAllHistory.checked = allSelected;
    elements.selectAllHistory.indeterminate = selectedCount > 0 && !allSelected;
    elements.selectAllHistory.disabled = state.historyLoading || !entries.length;
  }
  elements.restoreHistory.disabled = state.historyLoading || !selectedCount;
  elements.deleteHistory.disabled = state.historyLoading || !selectedCount;
  elements.exportHistory.disabled = state.historyLoading || !entries.some((entry) => !entry.job?.error);
  elements.clearHistory.disabled = state.historyLoading || !state.historyAllCount;
  elements.restoreHistory.innerHTML = `${icon('undo-2')} Restore selected${selectedCount ? ` (${selectedCount})` : ''}`;
  elements.deleteHistory.innerHTML = `${icon('trash-2')} Delete selected${selectedCount ? ` (${selectedCount})` : ''}`;
  refreshIcons();
}

async function loadHistory({ silent = false, preserveSelection = false } = {}) {
  if (!elements.historyBody) return;
  const requestId = state.historyRequest + 1;
  state.historyRequest = requestId;
  const selectedIds = preserveSelection
    ? new Set(state.historyEntries.filter((entry) => entry.selected).map((entry) => entry.id))
    : new Set();
  state.historyLoading = true;
  state.historyError = '';
  renderHistory();
  const parameters = new URLSearchParams({
    status: state.historyFilter,
    limit: '1000',
  });
  if (state.historyQuery) parameters.set('q', state.historyQuery);
  try {
    const response = await fetch(`/api/history?${parameters.toString()}`, { cache: 'no-store' });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || 'History could not be loaded.');
    if (requestId !== state.historyRequest) return;
    state.historyEntries = (payload.items || []).map((entry) => ({
      ...entry,
      selected: selectedIds.has(entry.id),
    }));
    state.historyTotal = Number(payload.total) || 0;
    state.historyAllCount = Number(payload.all_count) || 0;
    state.historyLoaded = true;
  } catch (error) {
    if (requestId !== state.historyRequest) return;
    state.historyError = error.message || 'Try opening History again.';
    if (!silent) showToast(state.historyError);
  } finally {
    if (requestId === state.historyRequest) {
      state.historyLoading = false;
      renderHistory();
    }
  }
}

async function saveJobsToHistory(jobs) {
  if (!elements.historyBody || !Array.isArray(jobs) || !jobs.length) return;
  const items = jobs
    .filter((job) => job && (job.job_link || (job.company && job.job_title)))
    .map((job) => {
      const { selected, _historyId, ...cleanJob } = job;
      return { job: cleanJob, status: historyStatusForJob(job) };
    });
  if (!items.length) return;
  try {
    for (let start = 0; start < items.length; start += 100) {
      const response = await fetch('/api/history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: items.slice(start, start + 100) }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || 'Local history could not be saved.');
      state.historyAllCount = Number(payload.all_count) || state.historyAllCount;
    }
    state.historyLoaded = false;
    state.historySaveWarned = false;
    if (state.view === 'history') {
      await loadHistory({ silent: true, preserveSelection: true });
    } else {
      renderHistory();
    }
  } catch (error) {
    if (!state.historySaveWarned) {
      state.historySaveWarned = true;
      showToast('The job is ready, but local history could not be saved');
    }
  }
}

function switchView(view) {
  const nextView = view === 'history' && elements.historyView ? 'history' : 'workspace';
  state.view = nextView;
  elements.workspaceView.hidden = nextView !== 'workspace';
  if (elements.historyView) elements.historyView.hidden = nextView !== 'history';
  [elements.workspaceViewButton, elements.historyViewButton].forEach((button) => {
    if (!button) return;
    const active = button.dataset.view === nextView;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  if (nextView === 'history') void loadHistory({ preserveSelection: true });
  refreshIcons();
}

function setAllHistorySelected(selected) {
  state.historyEntries.forEach((entry) => { entry.selected = selected; });
  renderHistory();
}

function restoreSelectedHistory() {
  const entries = state.historyEntries.filter((entry) => entry.selected);
  if (!entries.length) return;
  let added = 0;
  let updated = 0;
  let skipped = 0;
  entries.slice().reverse().forEach((entry) => {
    const job = { ...(entry.job || {}), selected: false, _historyId: entry.id };
    const existingIndex = job.job_link
      ? findJobIndexByLink(job.job_link)
      : state.jobs.findIndex((item) => item._historyId === entry.id);
    if (existingIndex >= 0) {
      if (elements.duplicateMode?.value === 'update') {
        state.jobs[existingIndex] = job;
        updated += 1;
      } else {
        skipped += 1;
      }
    } else {
      state.jobs.push(job);
      added += 1;
    }
  });
  state.filter = 'all';
  render();
  switchView('workspace');
  showToast(`${added} restored${updated ? `, ${updated} updated` : ''}${skipped ? `, ${skipped} already here` : ''}`);
}

async function downloadHistory() {
  const jobs = state.historyEntries
    .map((entry) => entry.job || {})
    .filter((job) => !job.error)
    .map((job) => jobWithSalaryDisplay(job, state.salaryMode, state.salaryHoursPerWeek));
  if (!jobs.length) return;
  elements.exportHistory.disabled = true;
  try {
    const response = await fetch('/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(jobs),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.error || 'The history file could not be created.');
    }
    await downloadResponse(response, 'job_history_export.xlsx');
    showToast('Your history Excel file is ready');
  } catch (error) {
    showToast(error.message);
  } finally {
    renderHistory();
  }
}

async function deleteSelectedHistory() {
  const ids = state.historyEntries.filter((entry) => entry.selected).map((entry) => entry.id);
  if (!ids.length) return;
  elements.deleteHistory.disabled = true;
  try {
    const response = await fetch('/api/history', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || 'Those history rows could not be deleted.');
    await loadHistory({ silent: true });
    showToast(`${payload.deleted || 0} ${Number(payload.deleted) === 1 ? 'job' : 'jobs'} deleted from history`);
  } catch (error) {
    showToast(error.message);
    renderHistory();
  }
}

async function clearAllHistory() {
  if (!state.historyAllCount) return;
  const confirmed = window.confirm(
    `Delete all ${state.historyAllCount} saved jobs from this computer? Your current results will stay.`,
  );
  if (!confirmed) return;
  elements.clearHistory.disabled = true;
  try {
    const response = await fetch('/api/history', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ all: true }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || 'History could not be cleared.');
    await loadHistory({ silent: true });
    showToast('History cleared');
  } catch (error) {
    showToast(error.message);
    renderHistory();
  }
}

async function scrapeOne(url) {
  const response = await fetch('/scrape', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  const result = await response.json().catch(() => ({ error: 'Linc received a response it could not read.' }));
  if (!response.ok && !result.error) result.error = `Linc could not finish that request (${response.status}).`;
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
  const payload = await response.json().catch(() => ({ error: 'Linc received a response it could not read.' }));
  if (!response.ok) throw new Error(payload.error || `Linc could not finish that request (${response.status}).`);
  return payload;
}

async function readScrapeJob(pollUrl) {
  const response = await fetch(pollUrl, { cache: 'no-store' });
  const payload = await response.json().catch(() => ({ error: 'Linc received a response it could not read.' }));
  if (!response.ok) {
    const error = new Error(payload.error || `Linc could not finish that request (${response.status}).`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

async function readScrapeJobWithRetry(pollUrl) {
  let lastError;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      return await readScrapeJob(pollUrl);
    } catch (error) {
      lastError = error;
      const retryable = !error.status || error.status >= 500;
      if (!retryable || attempt === 2) throw error;
      await wait(500 * (attempt + 1));
    }
  }
  throw lastError;
}

function applyScrapeSnapshot(snapshot, plan, appliedItems, dateApplied) {
  const changedJobs = [];
  (snapshot.items || []).forEach((item, index) => {
    if (!['completed', 'failed'].includes(item.status) || appliedItems.has(index)) return;
    const target = plan[index];
    if (!target) return;
    const result = {
      ...(item.result || { error: 'Linc could not read this job page.' }),
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
    changedJobs.push(result);
  });
  return changedJobs;
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
      const changedJobs = applyScrapeSnapshot(snapshot, plan, appliedItems, dateApplied);
      const settled = (snapshot.items || []).filter((item) => !['queued', 'running'].includes(item.status)).length;
      const processed = skipped + settled;
      elements.progressBar.style.width = `${Math.round((processed / urls.length) * 100)}%`;
      elements.progressText.textContent = `${processed} of ${urls.length}`;
      if (changedJobs.length) {
        render();
        await saveJobsToHistory(changedJobs);
      }
      if (['completed', 'cancelled'].includes(snapshot.status)) {
        finalStatus = snapshot.status;
        break;
      }
      await wait(600);
      snapshot = await readScrapeJobWithRetry(snapshot.poll_url || `/api/jobs/${snapshot.job_id}`);
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
    if (!response.ok) throw new Error(payload.error || 'Linc could not stop this batch.');
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
  try {
    const retried = await scrapeOne(current.job_link);
    retried.selected = Boolean(current.selected);
    state.jobs[index] = retried;
    await saveJobsToHistory([retried]);
    showToast(jobStatus(retried) === 'ready' ? 'Job updated' : 'This job still needs a look');
  } catch (error) {
    showToast('Linc lost the connection. The existing row was left unchanged.');
  } finally {
    state.processing = false;
    render();
  }
}

async function retryAllErrors() {
  if (state.processing) return;
  const indexes = state.jobs.map((job, index) => jobStatus(job) !== 'ready' ? index : -1).filter((index) => index >= 0);
  if (!indexes.length) return;
  state.processing = true;
  render();
  let connectionFailures = 0;
  const updatedJobs = [];
  try {
    for (const index of indexes) {
      const current = state.jobs[index];
      if (!current.job_link) continue;
      try {
        const retried = await scrapeOne(current.job_link);
        retried.selected = Boolean(current.selected);
        state.jobs[index] = retried;
        updatedJobs.push(retried);
      } catch (error) {
        connectionFailures += 1;
      }
    }
  } finally {
    await saveJobsToHistory(updatedJobs);
    state.processing = false;
    render();
  }
  const remaining = state.jobs.filter((job) => jobStatus(job) !== 'ready').length;
  if (connectionFailures) {
    showToast(`${connectionFailures} ${connectionFailures === 1 ? 'row was' : 'rows were'} left unchanged after a connection problem`);
  } else {
    showToast(remaining ? `${remaining} ${remaining === 1 ? 'row still needs' : 'rows still need'} a look` : 'Everything is ready now');
  }
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
    if (!response.ok) throw new Error(payload.error || 'Linc could not save this row for review.');
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
    if (!response.ok) throw new Error('Linc could not load your browser captures.');
    const payload = await response.json();
    const captures = Array.isArray(payload.jobs) ? payload.jobs : [];
    let added = 0;
    let updated = 0;
    const historyJobs = [];
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
      historyJobs.push(incoming);
    });

    render();
    await saveJobsToHistory(historyJobs);
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
      throw new Error(detail.error || 'Linc could not create the Excel file.');
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
      throw new Error(detail.error || 'Linc could not update this tracker.');
    }
    const blob = await response.blob();
    const added = response.headers.get('X-JobLink-Added') || '0';
    const skipped = response.headers.get('X-JobLink-Skipped') || '0';
    const updated = response.headers.get('X-JobLink-Updated') || '0';
    const outputName = filenameFromDisposition(response.headers.get('Content-Disposition')) || updatedWorkbookName(workbookFile.name);
    const saveResult = await saveBlobToSelectedWorkbook(blob);
    const savedToSelected = saveResult === 'saved';
    if (saveResult === 'download') {
      downloadBlob(blob, outputName);
      state.workbookHandle = null;
      state.workbookFile = new File([blob], outputName, { type: blob.type || workbookFile.type });
      elements.workbookFile.value = '';
      elements.workbookName.textContent = `${outputName} downloaded - original unchanged`;
    }
    const destination = savedToSelected ? ' in your original tracker' : ' in the downloaded copy';
    showToast(`${added} added${Number(updated) ? `, ${updated} updated` : ''}${Number(skipped) ? `, ${skipped} left unchanged` : ''}${destination}`);
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
      const displayedJob = jobWithSalaryDisplay(
        cleanJob,
        state.salaryMode,
        state.salaryHoursPerWeek,
      );
      return {
        ...displayedJob,
        date_applied: appliedDate || displayedJob.date_applied,
      };
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

function canOverwriteWorkbook() {
  return Boolean(state.workbookHandle?.createWritable);
}

async function saveBlobToSelectedWorkbook(blob) {
  if (!canOverwriteWorkbook()) return 'download';
  try {
    const writable = await state.workbookHandle.createWritable();
    await writable.write(blob);
    await writable.close();
    state.workbookFile = await state.workbookHandle.getFile();
    elements.workbookName.textContent = `${state.workbookFile.name} updated`;
    return 'saved';
  } catch (error) {
    throw new Error('Close the tracker in Excel, then choose Update original again.');
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
      elements.workbookName.textContent = `${state.workbookFile.name} selected - original will be updated`;
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
    if (!response.ok) throw new Error(payload.error || 'Linc could not save your feedback.');
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
  void saveJobsToHistory([job]);
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
  if (elements.otherAddMenu) elements.otherAddMenu.open = false;
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
  void saveJobsToHistory([job]);
  showToast('Job added');
}

elements.links.addEventListener('input', (event) => {
  if (
    !changingLinksProgrammatically
    && !['historyUndo', 'historyRedo'].includes(event.inputType)
  ) {
    linkPasteRedo.length = 0;
  }
  validateInput();
  saveSession();
});
elements.links.addEventListener('paste', handleLinksPaste);
elements.links.addEventListener('keydown', handleLinksHistoryShortcut);
elements.extract.addEventListener('click', processLinks);
if (elements.cancelJob) elements.cancelJob.addEventListener('click', cancelActiveJob);
elements.download.addEventListener('click', downloadExcel);
elements.appendWorkbook.addEventListener('click', appendToWorkbook);
elements.chooseWorkbook.addEventListener('click', chooseWorkbook);
if (elements.reportSelected) elements.reportSelected.addEventListener('click', reportSelectedJobs);
if (elements.duplicateMode) {
  elements.duplicateMode.addEventListener('change', () => {
    saveSession();
    if (elements.trackerSettings) elements.trackerSettings.open = false;
  });
}
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
elements.salaryModeButtons.forEach((button) => {
  button.addEventListener('click', () => {
    state.salaryMode = normalizeSalaryMode(button.dataset.salaryMode);
    render();
  });
});
if (elements.salaryHoursPerWeek) {
  elements.salaryHoursPerWeek.addEventListener('input', () => {
    state.salaryHoursPerWeek = normalizeHoursPerWeek(elements.salaryHoursPerWeek.value);
    refreshSalaryCells();
    saveSession();
  });
  elements.salaryHoursPerWeek.addEventListener('change', () => {
    state.salaryHoursPerWeek = normalizeHoursPerWeek(elements.salaryHoursPerWeek.value);
    render();
  });
}
elements.retryAll.addEventListener('click', retryAllErrors);
elements.loadCaptures.addEventListener('click', () => {
  if (elements.otherAddMenu) elements.otherAddMenu.open = false;
  void loadCaptures();
});
elements.clearResults.addEventListener('click', () => {
  state.jobs = state.jobs.filter((job) => !job.selected);
  render();
});
elements.workbookFile.addEventListener('change', () => {
  const file = elements.workbookFile.files[0] || null;
  state.workbookFile = file;
  state.workbookHandle = null;
  elements.workbookName.textContent = file
    ? `${file.name} selected - updated copy will download`
    : 'No tracker selected';
  render();
});
elements.clear.addEventListener('click', () => {
  elements.links.value = '';
  linkPasteHistory.length = 0;
  linkPasteRedo.length = 0;
  render();
});
elements.appliedDate.addEventListener('change', () => {
  const appliedDate = selectedAppliedDate();
  if (appliedDate) state.jobs.forEach((job) => { job.date_applied = appliedDate; });
  render();
  void saveJobsToHistory(state.jobs);
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
    void saveJobsToHistory([job]);
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
elements.body.addEventListener('focusout', (event) => {
  const editable = event.target.closest('.editable');
  if (!editable) return;
  const row = editable.closest('tr');
  const job = state.jobs[Number(row.dataset.index)];
  if (job) void saveJobsToHistory([job]);
});

if (elements.workspaceViewButton) {
  elements.workspaceViewButton.addEventListener('click', () => switchView('workspace'));
}
if (elements.historyViewButton) {
  elements.historyViewButton.addEventListener('click', () => switchView('history'));
}
if (elements.historySearch) {
  elements.historySearch.addEventListener('input', () => {
    window.clearTimeout(historySearchTimer);
    historySearchTimer = window.setTimeout(() => {
      state.historyQuery = elements.historySearch.value.trim();
      void loadHistory();
    }, 250);
  });
}
if (elements.historyStatusFilter) {
  elements.historyStatusFilter.addEventListener('change', () => {
    state.historyFilter = elements.historyStatusFilter.value;
    void loadHistory();
  });
}
if (elements.selectAllHistory) {
  elements.selectAllHistory.addEventListener('change', () => {
    setAllHistorySelected(elements.selectAllHistory.checked);
  });
}
if (elements.restoreHistory) elements.restoreHistory.addEventListener('click', restoreSelectedHistory);
if (elements.exportHistory) elements.exportHistory.addEventListener('click', downloadHistory);
if (elements.deleteHistory) elements.deleteHistory.addEventListener('click', deleteSelectedHistory);
if (elements.clearHistory) elements.clearHistory.addEventListener('click', clearAllHistory);
if (elements.historyBody) {
  elements.historyBody.addEventListener('change', (event) => {
    const checkbox = event.target.closest('.select-history-row');
    if (!checkbox) return;
    const row = checkbox.closest('tr');
    const id = Number(row.dataset.historyId);
    const entry = state.historyEntries.find((item) => item.id === id);
    if (entry) entry.selected = checkbox.checked;
    renderHistory();
  });
}

fetch('/health')
  .then((response) => { if (response.ok) elements.health.classList.add('is-online'); })
  .catch(() => {});

elements.appliedDate.value = todayIso();
restoreSession();
render();
renderHistory();
void loadHistory({ silent: true });
