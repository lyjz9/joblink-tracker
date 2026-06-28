const state = {
  jobs: [],
  processing: false,
  workbookFile: null,
  workbookHandle: null,
};

const elements = {
  links: document.querySelector('#jobLinks'),
  appliedDate: document.querySelector('#appliedDate'),
  counter: document.querySelector('#linkCounter'),
  validation: document.querySelector('#validationMessage'),
  extract: document.querySelector('#extractButton'),
  clear: document.querySelector('#clearButton'),
  clearResults: document.querySelector('#clearResultsButton'),
  download: document.querySelector('#downloadButton'),
  chooseWorkbook: document.querySelector('#chooseWorkbookButton'),
  workbookFile: document.querySelector('#workbookFile'),
  workbookName: document.querySelector('#workbookName'),
  appendWorkbook: document.querySelector('#appendWorkbookButton'),
  retryAll: document.querySelector('#retryAllButton'),
  progress: document.querySelector('#progress'),
  progressBar: document.querySelector('#progressBar'),
  progressText: document.querySelector('#progressText'),
  body: document.querySelector('#resultsBody'),
  table: document.querySelector('#tableWrap'),
  empty: document.querySelector('#emptyState'),
  total: document.querySelector('#totalCount'),
  ready: document.querySelector('#readyCount'),
  review: document.querySelector('#reviewCount'),
  error: document.querySelector('#errorCount'),
  toast: document.querySelector('#toast'),
  health: document.querySelector('#healthStatus'),
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
    .filter((value) => value && !seen.has(value) && seen.add(value));
}

function validateInput() {
  const urls = urlsFromInput();
  const hasTextWithoutUrl = elements.links.value.trim() && !urls.length;
  elements.counter.textContent = `${urls.length} / 20`;
  elements.validation.textContent = hasTextWithoutUrl
    ? 'No valid web address was found.'
    : urls.length > 20
      ? 'Process up to 20 links at a time.'
      : '';
  elements.extract.disabled = state.processing || !urls.length || urls.length > 20;
  elements.clear.disabled = state.processing || !elements.links.value;
  return urls;
}

function jobStatus(job) {
  if (job.error) return 'error';
  if ((job.review_issues && job.review_issues.length) || job.review_notes) return 'review';
  const required = ['company', 'job_title', 'location'];
  return required.some((key) => missingValue(job[key])) || looksSuspicious(job) ? 'review' : 'ready';
}

function badge(status) {
  const labels = { ready: 'Ready', review: 'Review', error: 'Error' };
  return `<span class="badge badge-${status}">${labels[status]}</span>`;
}

function editableCell(job, key) {
  const value = job[key] || 'n/a';
  const muted = String(value).toLowerCase() === 'n/a' ? ' muted-value' : '';
  return `<div class="editable${muted}" contenteditable="true" data-key="${key}" spellcheck="false">${escapeHtml(value)}</div>`;
}

function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = String(value ?? '');
  return div.innerHTML;
}

function render() {
  elements.body.innerHTML = state.jobs.map((job, index) => {
    const status = jobStatus(job);
    const detail = job.error || job.review_notes || '';
    const canRetry = status === 'error' || status === 'review';
    return `
      <tr data-index="${index}">
        <td class="select-cell">
          <input class="select-row" type="checkbox" aria-label="Select result row" ${job.selected ? 'checked' : ''}>
        </td>
        <td>${badge(status)}${detail ? `<span class="${status === 'error' ? 'error-detail' : 'review-detail'}">${escapeHtml(detail)}</span>` : ''}</td>
        <td>${editableCell(job, 'company')}</td>
        <td>${editableCell(job, 'job_title')}</td>
        <td>${editableCell(job, 'location')}</td>
        <td>${editableCell(job, 'work_type')}</td>
        <td>${editableCell(job, 'salary')}</td>
        <td>${escapeHtml(job.source || 'n/a')}</td>
        <td>
          <div class="row-actions">
            ${canRetry ? `<button class="icon-button retry-row" type="button" title="Retry extraction" aria-label="Retry extraction">${icon('rotate-cw')}</button>` : ''}
            <a class="icon-button" href="${escapeHtml(job.job_link || '#')}" target="_blank" rel="noopener noreferrer" title="Open job posting" aria-label="Open job posting">${icon('external-link')}</a>
            <button class="icon-button remove-row" type="button" title="Remove row" aria-label="Remove row">${icon('x')}</button>
          </div>
        </td>
      </tr>`;
  }).join('');

  const counts = state.jobs.reduce((result, job) => {
    result[jobStatus(job)] += 1;
    return result;
  }, { ready: 0, review: 0, error: 0 });
  elements.total.textContent = state.jobs.length;
  elements.ready.textContent = counts.ready;
  elements.review.textContent = counts.review;
  elements.error.textContent = counts.error;
  elements.table.hidden = !state.jobs.length;
  elements.empty.hidden = Boolean(state.jobs.length);
  const hasExportableJobs = state.jobs.some((job) => !job.error);
  const hasSelectedJobs = state.jobs.some((job) => job.selected);
  elements.download.disabled = !hasExportableJobs;
  elements.appendWorkbook.disabled = state.processing || !hasExportableJobs || !state.workbookFile;
  elements.retryAll.disabled = state.processing || !state.jobs.some((job) => jobStatus(job) !== 'ready');
  elements.clearResults.disabled = state.processing || !hasSelectedJobs;
  validateInput();
  refreshIcons();
}

async function scrapeOne(url) {
  const response = await fetch('/scrape', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  const result = await response.json().catch(() => ({ error: 'The server returned an unreadable response.' }));
  if (!response.ok && !result.error) result.error = `Request failed (${response.status}).`;
  return { ...result, job_link: result.job_link || url, date_applied: selectedAppliedDate() || result.date_applied };
}

async function processLinks() {
  const urls = validateInput();
  if (!urls.length || state.processing) return;
  state.processing = true;
  elements.progress.hidden = false;
  elements.progressBar.style.width = '0%';
  render();

  for (let index = 0; index < urls.length; index += 1) {
    elements.progressText.textContent = `${index + 1} of ${urls.length}`;
    const job = await scrapeOne(urls[index]);
    state.jobs.push(job);
    elements.progressBar.style.width = `${Math.round(((index + 1) / urls.length) * 100)}%`;
    render();
  }

  state.processing = false;
  elements.progressText.textContent = 'Complete';
  render();
  validateInput();
  showToast(`${urls.length} ${urls.length === 1 ? 'job' : 'jobs'} processed`);
  setTimeout(() => { elements.progress.hidden = true; }, 1200);
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
  showToast(jobStatus(retried) === 'ready' ? 'Job extracted' : 'The job still needs review');
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
  showToast(remaining ? `${remaining} ${remaining === 1 ? 'row' : 'rows'} still need review` : 'All review rows cleared');
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
      throw new Error(detail.error || 'Export failed.');
    }
    await downloadResponse(response, 'job_tracker_export.xlsx');
    showToast('Excel file created');
  } catch (error) {
    showToast(error.message);
  } finally {
    elements.download.disabled = false;
  }
}

async function appendToWorkbook() {
  const jobs = exportableJobs();
  if (!jobs.length || !state.workbookFile) return;
  elements.appendWorkbook.disabled = true;
  try {
    const formData = new FormData();
    formData.append('workbook', state.workbookFile);
    formData.append('jobs', JSON.stringify(jobs));
    const response = await fetch('/append-workbook', {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.error || 'Tracker update failed.');
    }
    const blob = await response.blob();
    const added = response.headers.get('X-JobLink-Added') || '0';
    const skipped = response.headers.get('X-JobLink-Skipped') || '0';
    const savedToSelected = await saveBlobToSelectedWorkbook(blob);
    if (!savedToSelected) {
      downloadBlob(blob, filenameFromDisposition(response.headers.get('Content-Disposition')) || updatedWorkbookName(state.workbookFile.name));
    }
    showToast(`${added} added${Number(skipped) ? `, ${skipped} skipped` : ''}${savedToSelected ? ' to tracker' : ''}`);
  } catch (error) {
    showToast(error.message);
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
    elements.workbookName.textContent = `${state.workbookFile.name} saved`;
    return true;
  } catch (error) {
    showToast('Could not save over the tracker. Close it in Excel and try again.');
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

elements.links.addEventListener('input', validateInput);
elements.extract.addEventListener('click', processLinks);
elements.download.addEventListener('click', downloadExcel);
elements.appendWorkbook.addEventListener('click', appendToWorkbook);
elements.chooseWorkbook.addEventListener('click', chooseWorkbook);
elements.retryAll.addEventListener('click', retryAllErrors);
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
});
elements.body.addEventListener('click', (event) => {
  const retry = event.target.closest('.retry-row');
  if (retry) {
    retryJob(Number(retry.closest('tr').dataset.index));
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
});

fetch('/health')
  .then((response) => { if (response.ok) elements.health.classList.add('is-online'); })
  .catch(() => {});

elements.appliedDate.value = todayIso();
render();
