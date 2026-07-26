(function attachLinkInputHelpers(root, factory) {
  const helpers = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = helpers;
  } else {
    root.JobLinkInput = helpers;
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function createLinkInputHelpers() {
  'use strict';

  const TRACKING_QUERY_PARAMETERS = new Set([
    'from',
    'gh_src',
    'ref',
    'refid',
    'source',
    'src',
    'trackingid',
    'trk',
    'utm_campaign',
    'utm_content',
    'utm_id',
    'utm_medium',
    'utm_source',
    'utm_term',
  ]);

  function cleanUrlCandidate(value) {
    return String(value || '')
      .replace(/&amp;/gi, '&')
      .replace(/[\u200b\u200c\u200d\ufeff]/g, '')
      .trim()
      .replace(/[.,;:!?\)\]\}\\]+$/g, '');
  }

  function linkKey(value) {
    const text = cleanUrlCandidate(value);
    if (!text) return '';
    try {
      const parsed = new URL(text);
      const host = parsed.hostname.toLowerCase().replace(/^www\./, '').replace(/\.$/, '');
      const path = parsed.pathname.replace(/\/+$/, '') || '/';
      if (host === 'linkedin.com' || host.endsWith('.linkedin.com')) {
        const jobId = path.match(/\/jobs\/view\/(?:.*-)?(\d{7,})(?:\/|$)/i);
        if (jobId) return `linkedin.com/jobs/view/${jobId[1]}`;
      }

      const queryPairs = [];
      parsed.searchParams.forEach((item, key) => {
        const normalizedKey = key.toLowerCase();
        if (TRACKING_QUERY_PARAMETERS.has(normalizedKey) || normalizedKey.startsWith('utm_')) return;
        queryPairs.push([key, item]);
      });
      queryPairs.sort((left, right) => {
        const keyOrder = left[0].toLowerCase().localeCompare(right[0].toLowerCase());
        return keyOrder || left[1].localeCompare(right[1]);
      });

      if ((host === 'indeed.com' || host.endsWith('.indeed.com')) && path.toLowerCase() === '/viewjob') {
        const jobKey = queryPairs.find(([key, item]) => key.toLowerCase() === 'jk' && item);
        if (jobKey) return `indeed.com/viewjob?jk=${jobKey[1].toLowerCase()}`;
      }

      const query = new URLSearchParams(queryPairs).toString();
      return `${host}${parsed.port ? `:${parsed.port}` : ''}${path}${query ? `?${query}` : ''}`;
    } catch (error) {
      return text.replace(/\/+$/, '').toLowerCase();
    }
  }

  function parseLinksFromText(value) {
    const seen = new Set();
    const urls = [];
    let duplicateCount = 0;
    let invalidCount = 0;
    const input = String(value || '')
      .replace(/&amp;/gi, '&')
      .replace(/[\u200b\u200c\u200d\ufeff]/g, '');
    const matches = input.match(/https?:\/\/(?:(?!https?:\/\/)[^\s<>"'\[\]])+/gi) || [];

    matches.forEach((value) => {
      const cleaned = cleanUrlCandidate(value);
      try {
        const parsed = new URL(cleaned);
        if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.hostname || cleaned.includes('\\')) {
          invalidCount += 1;
          return;
        }
        const key = linkKey(cleaned);
        if (!key) {
          invalidCount += 1;
          return;
        }
        if (seen.has(key)) {
          duplicateCount += 1;
          return;
        }
        seen.add(key);
        urls.push(cleaned);
      } catch (error) {
        invalidCount += 1;
      }
    });
    return { urls, duplicateCount, invalidCount };
  }

  function mergePastedLinks(existingText, clipboardText) {
    const currentText = String(existingText || '');
    const pasted = parseLinksFromText(clipboardText);
    if (!pasted.urls.length) {
      return {
        handled: false,
        text: currentText,
        addedCount: 0,
        duplicateCount: pasted.duplicateCount,
        invalidCount: pasted.invalidCount,
      };
    }

    const existingKeys = new Set(parseLinksFromText(currentText).urls.map(linkKey));
    const additions = [];
    let duplicateCount = pasted.duplicateCount;
    pasted.urls.forEach((url) => {
      const key = linkKey(url);
      if (existingKeys.has(key)) {
        duplicateCount += 1;
        return;
      }
      existingKeys.add(key);
      additions.push(url);
    });

    const base = currentText.replace(/\s+$/, '');
    const text = additions.length
      ? `${base ? `${base}\n` : ''}${additions.join('\n')}\n`
      : currentText;
    return {
      handled: true,
      text,
      addedCount: additions.length,
      duplicateCount,
      invalidCount: pasted.invalidCount,
    };
  }

  return {
    cleanUrlCandidate,
    linkKey,
    mergePastedLinks,
    parseLinksFromText,
  };
}));
