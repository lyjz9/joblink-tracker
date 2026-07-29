const assert = require('assert');
const {
  convertSalary,
  jobWithSalaryDisplay,
  normalizeHoursPerWeek,
  normalizeSalaryMode,
} = require('../scraper/static/salary_conversion.js');

assert.strictEqual(normalizeSalaryMode('YEARLY'), 'yearly');
assert.strictEqual(normalizeSalaryMode('unknown'), 'original');
assert.strictEqual(normalizeHoursPerWeek(20), 20);
assert.strictEqual(normalizeHoursPerWeek(37.6), 37.5);
assert.strictEqual(normalizeHoursPerWeek(0), 1);
assert.strictEqual(normalizeHoursPerWeek(100), 80);

assert.strictEqual(
  convertSalary('$20 - $25/hour', 'original', 40).value,
  '$20 - $25/hour',
);
assert.strictEqual(
  convertSalary('$20 - $25/hour', 'yearly', 40).value,
  '~$41,600 - $52,000/year',
);
assert.strictEqual(
  convertSalary('$20 - $25/hour', 'yearly', 20).value,
  '~$20,800 - $26,000/year',
);
assert.strictEqual(
  convertSalary('$70,000 - $85,000/year', 'hourly', 40).value,
  '~$33.65 - $40.87/hour',
);
assert.strictEqual(
  convertSalary('$70,000 - $85,000/year', 'hourly', 20).value,
  '~$67.31 - $81.73/hour',
);
assert.strictEqual(
  convertSalary('$1,800 - $4,500 per week', 'yearly', 40).value,
  '~$93,600 - $234,000/year',
);
assert.strictEqual(
  convertSalary('USD $20.00/hr - $25.00/hr', 'hourly', 40).value,
  'USD $20 - $25/hour',
);
assert.strictEqual(
  convertSalary('$20/hour', 'yearly', 20).value,
  '~$20,800/year',
);

const missingPeriod = convertSalary('$55,341 - $68,270', 'hourly', 40);
assert.strictEqual(missingPeriod.value, '$55,341 - $68,270');
assert.strictEqual(missingPeriod.convertible, false);
assert.strictEqual(missingPeriod.reason, 'missing_period');

const bonus = convertSalary('$70,000/year + bonus', 'hourly', 40);
assert.strictEqual(bonus.value, '$70,000/year + bonus');
assert.strictEqual(bonus.convertible, false);

const originalJob = {
  company: 'Example Company',
  salary: '$20 - $25/hour',
};
const yearlyJob = jobWithSalaryDisplay(originalJob, 'yearly', 20);
assert.strictEqual(yearlyJob.salary, '~$20,800 - $26,000/year');
assert.strictEqual(originalJob.salary, '$20 - $25/hour');
assert.notStrictEqual(yearlyJob, originalJob);

console.log('Frontend salary-conversion tests passed');
