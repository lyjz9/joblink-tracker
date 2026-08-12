(function sourceTrackingModule(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.JobSourceTracking = api;
}(typeof window !== 'undefined' ? window : globalThis, () => {
  const DISCOVERY_LABELS = new Set([
    'LinkedIn', 'Indeed', 'Glassdoor', 'ZipRecruiter', 'Monster', 'Wellfound',
    'Upwork', 'SimplyHired', 'Dice', 'Handshake', 'Google Jobs', 'Jooble',
  ]);

  const DISCOVERY_QUERY_ALIASES = [
    ['linkedin', 'LinkedIn'],
    ['indeed', 'Indeed'],
    ['glassdoor', 'Glassdoor'],
    ['ziprecruiter', 'ZipRecruiter'],
    ['monster', 'Monster'],
    ['wellfound', 'Wellfound'],
    ['angellist', 'Wellfound'],
    ['upwork', 'Upwork'],
    ['simplyhired', 'SimplyHired'],
    ['dice', 'Dice'],
    ['handshake', 'Handshake'],
    ['google_jobs', 'Google Jobs'],
    ['google jobs', 'Google Jobs'],
    ['jooble', 'Jooble'],
  ];

  const DISCOVERY_QUERY_KEYS = new Set([
    'utm_source', 'source', 'src', 'ref', 'referrer', 'lever-source', '__jvsd', '__jvst',
  ]);

  const PLATFORM_DOMAINS = [
    ['linkedin.com', 'LinkedIn'],
    ['indeed.com', 'Indeed'],
    ['glassdoor.com', 'Glassdoor'],
    ['ziprecruiter.com', 'ZipRecruiter'],
    ['monster.com', 'Monster'],
    ['wellfound.com', 'Wellfound'],
    ['upwork.com', 'Upwork'],
    ['simplyhired.com', 'SimplyHired'],
    ['dice.com', 'Dice'],
    ['joinhandshake.com', 'Handshake'],
    ['greenhouse.io', 'Greenhouse'],
    ['greenhouse.com', 'Greenhouse'],
    ['lever.co', 'Lever'],
    ['myworkdayjobs.com', 'Workday'],
    ['ashbyhq.com', 'Ashby'],
    ['smartrecruiters.com', 'SmartRecruiters'],
    ['workable.com', 'Workable'],
    ['bamboohr.com', 'BambooHR'],
    ['dayforcehcm.com', 'Dayforce'],
    ['icims.com', 'iCIMS'],
    ['breezy.hr', 'Breezy'],
    ['jobvite.com', 'Jobvite'],
    ['oraclecloud.com', 'Oracle Recruiting'],
    ['taleo.net', 'Taleo'],
    ['eploy.net', 'Eploy'],
    ['eightfold.ai', 'Eightfold'],
    ['successfactors.com', 'SAP SuccessFactors'],
  ];

  const KNOWN_LABELS = new Map([
    ...Array.from(DISCOVERY_LABELS, (label) => [label.toLowerCase(), label]),
    ...[
      'N/A', 'Company Website', 'Referral', 'Other', 'Greenhouse', 'Lever',
      'Workday', 'Ashby', 'SmartRecruiters', 'Workable', 'BambooHR', 'Dayforce',
      'iCIMS', 'Breezy', 'Jobvite', 'Oracle Recruiting', 'Taleo', 'Eploy',
      'Eightfold', 'SAP SuccessFactors', 'Google Jobs', 'Jooble',
    ].map((label) => [label.toLowerCase(), label]),
  ]);

  function normalizeSourceLabel(value) {
    const text = String(value || '').replace(/\s+/g, ' ').trim();
    if (!text || ['auto', 'auto from link'].includes(text.toLowerCase())) return '';
    if (['n/a', 'na', 'none', 'null'].includes(text.toLowerCase())) return 'N/A';
    return KNOWN_LABELS.get(text.toLowerCase()) || text.slice(0, 80);
  }

  function hostnameFromUrl(value) {
    try {
      return new URL(String(value || '')).hostname.toLowerCase().replace(/^www\./, '');
    } catch (error) {
      return '';
    }
  }

  function inferApplicationPortal(url, legacySource = '') {
    const host = hostnameFromUrl(url);
    if (host) {
      const match = PLATFORM_DOMAINS.find(([domain]) => host === domain || host.endsWith(`.${domain}`));
      return match ? match[1] : 'Company Website';
    }
    const legacy = normalizeSourceLabel(legacySource);
    return legacy && legacy !== 'N/A' ? legacy : 'Company Website';
  }

  function inferFoundOn(url, selected = '', legacySource = '') {
    const explicit = normalizeSourceLabel(selected);
    if (explicit) return explicit;
    try {
      const parsed = new URL(String(url || ''));
      for (const [key, rawValue] of parsed.searchParams.entries()) {
        if (!DISCOVERY_QUERY_KEYS.has(key.toLowerCase())) continue;
        const value = rawValue.toLowerCase();
        const match = DISCOVERY_QUERY_ALIASES.find(([marker]) => value.includes(marker));
        if (match) return match[1];
        if (['careersite', 'career site', 'company website'].includes(value)) {
          return 'Company Website';
        }
      }
    } catch (error) {
      // Invalid or missing URLs fall through to legacy data.
    }
    const legacy = normalizeSourceLabel(legacySource);
    if (DISCOVERY_LABELS.has(legacy)) return legacy;
    const portal = inferApplicationPortal(url, legacySource);
    return DISCOVERY_LABELS.has(portal) ? portal : 'N/A';
  }

  function normalizeJobSources(job, selectedFoundOn = '') {
    const source = job && typeof job === 'object' ? job : {};
    const portal = normalizeSourceLabel(source.application_portal)
      || inferApplicationPortal(source.job_link, source.source);
    const foundOn = normalizeSourceLabel(selectedFoundOn)
      || normalizeSourceLabel(source.found_on)
      || inferFoundOn(source.job_link, '', source.source);
    return {
      ...source,
      found_on: foundOn,
      application_portal: portal,
      source: portal,
    };
  }

  return {
    DISCOVERY_LABELS,
    inferApplicationPortal,
    inferFoundOn,
    normalizeJobSources,
    normalizeSourceLabel,
  };
}));
