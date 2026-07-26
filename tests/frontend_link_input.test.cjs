const assert = require('assert');
const {
  linkKey,
  mergePastedLinks,
  parseLinksFromText,
} = require('../scraper/static/link_input.js');

const first = 'https://company.example/jobs/operations-analyst?utm_source=linkedin';
const second = 'https://company.example/jobs/data-analyst';

const firstPaste = mergePastedLinks('', first);
assert.strictEqual(firstPaste.handled, true);
assert.strictEqual(firstPaste.addedCount, 1);
assert.strictEqual(firstPaste.text, `${first}\n`);

const secondPaste = mergePastedLinks(firstPaste.text, second);
assert.strictEqual(secondPaste.addedCount, 1);
assert.strictEqual(secondPaste.text, `${first}\n${second}\n`);

const bulkPaste = mergePastedLinks(
  '',
  `First role: ${first}, Second role: ${second}\nhttps://company.example/jobs/third`,
);
assert.deepStrictEqual(
  parseLinksFromText(bulkPaste.text).urls,
  [first, second, 'https://company.example/jobs/third'],
);

const trackedDuplicate = mergePastedLinks(
  `${first}\n`,
  'https://company.example/jobs/operations-analyst?source=careers&trk=jobs',
);
assert.strictEqual(trackedDuplicate.addedCount, 0);
assert.strictEqual(trackedDuplicate.duplicateCount, 1);
assert.strictEqual(trackedDuplicate.text, `${first}\n`);

const linkedInPlain = 'https://www.linkedin.com/jobs/view/4443868424/';
const linkedInSlug = (
  'https://linkedin.com/jobs/view/entry-level-analyst-at-example-4443868424'
  + '?utm_campaign=jobs'
);
assert.strictEqual(linkKey(linkedInPlain), linkKey(linkedInSlug));

const malformed = mergePastedLinks('', 'https://?');
assert.strictEqual(malformed.handled, false);
assert.strictEqual(malformed.invalidCount, 1);

const ordinaryText = mergePastedLinks(firstPaste.text, 'notes about tomorrow');
assert.strictEqual(ordinaryText.handled, false);
assert.strictEqual(ordinaryText.text, firstPaste.text);

const htmlEscaped = parseLinksFromText(
  'https://company.example/jobs/123?one=1&amp;two=2',
);
assert.strictEqual(
  htmlEscaped.urls[0],
  'https://company.example/jobs/123?one=1&two=2',
);

const twentyOneLinks = Array.from(
  { length: 21 },
  (_value, index) => `https://company.example/jobs/${index + 1}`,
).join('\n');
assert.strictEqual(parseLinksFromText(twentyOneLinks).urls.length, 21);

console.log('Frontend link-input tests passed');
