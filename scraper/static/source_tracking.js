(() => {
  const portalDomains = [
    ['builtinnyc.com', 'Built In NYC'],
    ['hiringcafe.com', 'Hiring Cafe'],
    ['joinhandshake.com', 'Handshake'],
    ['oraclecloud.com', 'Oracle Recruiting'],
    ['taleo.net', 'Taleo'],
    ['tal.net', 'TAL'],
    ['eploy.net', 'Eploy'],
    ['eightfold.ai', 'Eightfold'],
    ['successfactors.com', 'SAP SuccessFactors'],
  ];

  const platformDomains = [
    ['greenhouse.io', 'Greenhouse'],
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
  ];

  function normalizePortal(value) {
    const text = String(value || '').trim();
    return ['n/a', 'na', 'none', 'null'].includes(text.toLowerCase()) ? '' : text;
  }

  function inferApplicationPortal(url, fallback = '') {
    try {
      const host = new URL(String(url || '')).hostname.toLowerCase().replace(/^www\./, '');
      for (const [domain, label] of platformDomains.concat(portalDomains)) {
        if (host === domain || host.endsWith(`.${domain}`)) return label;
      }
      return host ? 'Company Website' : (normalizePortal(fallback) || 'Company Website');
    } catch (_error) {
      return normalizePortal(fallback) || 'Company Website';
    }
  }

  function normalizeJobSources(job) {
    const source = job && typeof job === 'object' ? job : {};
    const normalized = { ...source };
    delete normalized.found_on;
    const currentPortal = normalizePortal(source.application_portal);
    const detectedPortal = inferApplicationPortal(source.job_link, source.source);
    const portal = !currentPortal || (currentPortal === 'Company Website' && detectedPortal !== currentPortal)
      ? detectedPortal
      : currentPortal;
    return {
      ...normalized,
      application_portal: portal,
      source: portal,
    };
  }

  window.JobSourceTracking = {
    inferApplicationPortal,
    normalizeJobSources,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.JobSourceTracking;
  }
})();
