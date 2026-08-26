const assert = require('assert');
const {
  inferApplicationPortal,
  normalizeJobSources,
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
  },
);

console.log('Frontend source-tracking tests passed');
