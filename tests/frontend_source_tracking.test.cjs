const assert = require('assert');
const {
  inferApplicationPortal,
  normalizeJobSources,
  mergeRefreshedJob,
} = require('../scraper/static/source_tracking.js');

const workday = 'https://example.wd5.myworkdayjobs.com/en-US/jobs/job/Analyst_R123';
assert.strictEqual(inferApplicationPortal(workday), 'Workday');
assert.strictEqual(inferApplicationPortal('https://jobs.ashbyhq.com/example/123'), 'Ashby');
assert.strictEqual(inferApplicationPortal('https://www.builtinnyc.com/job/data-analyst/10804121'), 'Built In NYC');
assert.strictEqual(inferApplicationPortal('https://hiringcafe.com/job/business-operations-analyst-hometap-boston-massachusetts-q3y3y9pl0rk2sdmy'), 'Hiring Cafe');
assert.strictEqual(inferApplicationPortal('https://blackrock.tal.net/vx/opp/12218/en-GB'), 'TAL');
assert.strictEqual(inferApplicationPortal('https://careers.example.com/jobs/123'), 'Company Website');
assert.deepStrictEqual(
  normalizeJobSources({ job_link: workday, source: 'LinkedIn', found_on: 'LinkedIn' }),
  {
    job_link: workday,
    source: 'Workday',
    application_portal: 'Workday',
    found_on: 'LinkedIn',
  },
);
assert.deepStrictEqual(
  normalizeJobSources({
    job_link: 'https://hiringcafe.com/job/task-associate-ulta-beauty-mobile-alabama-5zqvmbrvot7v5jsp',
    application_portal: 'Company Website',
    source: 'Company Website',
  }),
  {
    job_link: 'https://hiringcafe.com/job/task-associate-ulta-beauty-mobile-alabama-5zqvmbrvot7v5jsp',
    application_portal: 'Hiring Cafe',
    source: 'Hiring Cafe',
    found_on: '',
  },
);

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const source = fs.readFileSync(path.join(__dirname, '../scraper/static/app.js'), 'utf8');
const original = {
  company: 'Example', job_title: 'Analyst', job_link: workday,
  date_applied: '10/01/2026', found_on: 'LinkedIn', status: 'Interview',
  follow_up: '10/25/2026', selected: true,
};
const refreshed = mergeRefreshedJob(original, {
  ...original, date_applied: '10/16/2026', found_on: '', status: '', follow_up: '',
  salary: '$85,000/yr', confidence: 'High',
});
for (const field of ['date_applied', 'found_on', 'status', 'follow_up', 'selected']) {
  assert.strictEqual(refreshed[field], original[field]);
}
assert.strictEqual(refreshed.salary, '$85,000/yr');

const context = {
  state: { jobs: [{ ...original }], processing: false, salaryMode: 'original', salaryHoursPerWeek: 40 },
  selectedAppliedDate: () => '10/16/2026',
  fetch: async () => ({ ok: true, json: async () => ({ company: 'Example', job_title: 'Analyst', salary: '$85,000/yr' }) }),
  trackedJob: normalizeJobSources, mergeRefreshedJob,
  jobWithSalaryDisplay: require('../scraper/static/salary_conversion.js').jobWithSalaryDisplay,
  render: () => {}, saveJobsToHistory: async () => {}, showToast: () => {}, jobStatus: () => 'ready',
};
vm.createContext(context);
function loadFunction(start, end) {
  const from = source.indexOf(start);
  const to = source.indexOf(end, from + start.length);
  assert.ok(from >= 0 && to > from);
  vm.runInContext(source.slice(from, to), context);
}
loadFunction('async function scrapeOne(', 'function wait(');
loadFunction('async function retryJob(', 'async function retryAllErrors(');
loadFunction('async function retryAllErrors(', 'async function reportJob(');
loadFunction('function applyScrapeSnapshot(', 'async function processLinks(');
loadFunction('function exportableJobs(', 'async function downloadResponse(');

(async () => {
  await vm.runInContext('retryJob(0)', context);
  for (const field of ['date_applied', 'found_on', 'status', 'follow_up', 'selected']) {
    assert.strictEqual(context.state.jobs[0][field], original[field], `Retry lost ${field}`);
  }
  context.jobStatus = () => 'review';
  await vm.runInContext('retryAllErrors()', context);
  assert.strictEqual(context.state.jobs[0].found_on, 'LinkedIn');
  vm.runInContext(`applyScrapeSnapshot(
    {items:[{status:'completed',result:{company:'Updated',job_title:'Analyst',found_on:'Indeed'}}]},
    [{url:'${workday}',action:'update',index:0}],new Set(),'10/16/2026')`, context);
  assert.strictEqual(context.state.jobs[0].company, 'Updated');
  assert.strictEqual(context.state.jobs[0].found_on, 'LinkedIn');
  assert.strictEqual(context.state.jobs[0].date_applied, '10/01/2026');
  context.state.jobs = [
    { ...original, selected: true },
    { ...original, date_applied: '10/05/2026', salary: '$25/hr' },
    { company: 'New', job_title: 'Analyst' },
  ];
  const exported = vm.runInContext('exportableJobs()', context);
  assert.deepStrictEqual(Array.from(exported, job => job.date_applied), ['10/01/2026', '10/05/2026', '10/16/2026']);
  assert.strictEqual(exported[0].selected, undefined);
  assert.strictEqual(context.state.jobs[0].selected, true);
  console.log('Frontend source-tracking tests passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
