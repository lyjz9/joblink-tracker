const assert = require('assert');
const {
  inferApplicationPortal,
  inferFoundOn,
  normalizeJobSources,
} = require('../scraper/static/source_tracking.js');

const workday = 'https://example.wd5.myworkdayjobs.com/en-US/jobs/job/Analyst_R123';
assert.strictEqual(inferApplicationPortal(workday), 'Workday');
assert.strictEqual(inferApplicationPortal('https://jobs.ashbyhq.com/example/123'), 'Ashby');
assert.strictEqual(inferApplicationPortal('https://careers.example.com/jobs/123'), 'Company Website');
assert.strictEqual(inferFoundOn(workday, 'LinkedIn'), 'LinkedIn');
assert.strictEqual(inferFoundOn(workday), 'N/A');
assert.strictEqual(inferFoundOn('https://www.linkedin.com/jobs/view/4443868424/'), 'LinkedIn');
assert.strictEqual(inferFoundOn(`${workday}?source=LinkedIn`), 'LinkedIn');
assert.strictEqual(
  inferFoundOn('https://apply.workable.com/example/j/123/?utm_source=google_jobs_apply'),
  'Google Jobs',
);
assert.strictEqual(inferFoundOn('https://careers.example.com/job/123?source=opaque-code'), 'N/A');
assert.deepStrictEqual(
  normalizeJobSources({ job_link: workday, source: 'LinkedIn' }),
  {
    job_link: workday,
    source: 'Workday',
    found_on: 'LinkedIn',
    application_portal: 'Workday',
  },
);

console.log('Frontend source-tracking tests passed');
