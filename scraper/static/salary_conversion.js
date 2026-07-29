(function attachSalaryConversionHelpers(root, factory) {
  const helpers = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = helpers;
  } else {
    root.JobSalaryDisplay = helpers;
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function createSalaryConversionHelpers() {
  'use strict';

  const MODES = new Set(['original', 'hourly', 'yearly']);
  const DEFAULT_HOURS_PER_WEEK = 40;
  const WEEKS_PER_YEAR = 52;
  const CURRENCY_SYMBOLS = {
    USD: '$',
    CAD: '$',
    AUD: '$',
    GBP: '\u00a3',
    EUR: '\u20ac',
    JPY: '\u00a5',
    INR: '\u20b9',
  };
  const PERIOD_PATTERNS = {
    hour: /(?:\/\s*(?:hours?|hrs?)\b|\b(?:per|an?)\s+(?:hours?|hrs?)\b|\bhourly\b)/i,
    week: /(?:\/\s*(?:weeks?|wks?)\b|\b(?:per|a)\s+(?:weeks?|wks?)\b|\bweekly\b)/i,
    month: /(?:\/\s*(?:months?|mos?)\b|\b(?:per|a)\s+(?:months?|mos?)\b|\bmonthly\b)/i,
    year: /(?:\/\s*(?:years?|yrs?)\b|\b(?:per|a)\s+(?:years?|yrs?)\b|\b(?:annual|annually|yearly|annum)\b)/i,
  };
  const NON_SALARY_PAY = /\b(?:bonus|commission|equity|stock|options?|fixed[-\s]?price|project\s+budget|one[-\s]?time)\b/i;

  function normalizeSalaryMode(value) {
    const mode = String(value || '').toLowerCase();
    return MODES.has(mode) ? mode : 'original';
  }

  function normalizeHoursPerWeek(value) {
    const hours = Number(value);
    if (!Number.isFinite(hours)) return DEFAULT_HOURS_PER_WEEK;
    return Math.min(80, Math.max(1, Math.round(hours * 4) / 4));
  }

  function parseSalary(value) {
    const original = String(value || '').replace(/\s+/g, ' ').trim();
    if (!original || ['n/a', 'none', 'null'].includes(original.toLowerCase())) {
      return { original, reason: 'missing' };
    }
    if (NON_SALARY_PAY.test(original)) {
      return { original, reason: 'non_salary_compensation' };
    }

    const periods = Object.entries(PERIOD_PATTERNS)
      .filter(([, pattern]) => pattern.test(original))
      .map(([period]) => period);
    if (periods.length !== 1) {
      return { original, reason: periods.length ? 'mixed_periods' : 'missing_period' };
    }

    const currencyCodes = Array.from(original.matchAll(/\b(USD|CAD|AUD|GBP|EUR|JPY|INR)\b/gi))
      .map((match) => match[1].toUpperCase());
    const currencySymbols = Array.from(original.matchAll(/[$\u00a3\u20ac\u00a5\u20b9]/g))
      .map((match) => match[0]);
    const codeSet = new Set(currencyCodes);
    const symbolSet = new Set(currencySymbols);
    if (codeSet.size > 1 || symbolSet.size > 1) {
      return { original, reason: 'mixed_currencies' };
    }

    const currencyCode = currencyCodes[0] || '';
    const currencySymbol = currencySymbols[0] || '';
    if (
      currencyCode
      && currencySymbol
      && CURRENCY_SYMBOLS[currencyCode] !== currencySymbol
    ) {
      return { original, reason: 'mixed_currencies' };
    }

    const amounts = [];
    const amountPattern = /(?:[$\u00a3\u20ac\u00a5\u20b9]\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)\s*([kK])?/g;
    for (const match of original.matchAll(amountPattern)) {
      const number = Number(match[1].replaceAll(',', ''));
      if (!Number.isFinite(number)) continue;
      amounts.push(number * (match[2] ? 1000 : 1));
    }
    if (!amounts.length || amounts.length > 2) {
      return { original, reason: 'unreadable_amount' };
    }

    return {
      original,
      amounts,
      currencyCode,
      currencySymbol,
      period: periods[0],
    };
  }

  function annualAmount(amount, sourcePeriod, hoursPerWeek) {
    if (sourcePeriod === 'hour') return amount * hoursPerWeek * WEEKS_PER_YEAR;
    if (sourcePeriod === 'week') return amount * WEEKS_PER_YEAR;
    if (sourcePeriod === 'month') return amount * 12;
    return amount;
  }

  function formatNumber(value, targetPeriod) {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 0,
      maximumFractionDigits: targetPeriod === 'hour' ? 2 : 0,
    }).format(value);
  }

  function formatCurrencyPrefix(parsed) {
    if (parsed.currencyCode && parsed.currencySymbol) {
      return `${parsed.currencyCode} ${parsed.currencySymbol}`;
    }
    if (parsed.currencyCode) return `${parsed.currencyCode} `;
    return parsed.currencySymbol || '';
  }

  function convertSalary(value, mode = 'original', hoursPerWeek = DEFAULT_HOURS_PER_WEEK) {
    const normalizedMode = normalizeSalaryMode(mode);
    const original = String(value || '').replace(/\s+/g, ' ').trim() || 'n/a';
    if (normalizedMode === 'original') {
      return {
        value: original,
        convertible: false,
        estimated: false,
        original,
      };
    }

    const parsed = parseSalary(original);
    if (!parsed.amounts) {
      return {
        value: original,
        convertible: false,
        estimated: false,
        original,
        reason: parsed.reason,
      };
    }

    const hours = normalizeHoursPerWeek(hoursPerWeek);
    const targetPeriod = normalizedMode === 'hourly' ? 'hour' : 'year';
    const convertedAmounts = parsed.amounts.map((amount) => {
      const annual = annualAmount(amount, parsed.period, hours);
      return targetPeriod === 'hour' ? annual / (hours * WEEKS_PER_YEAR) : annual;
    });
    const formattedAmounts = convertedAmounts.map((amount) => formatNumber(amount, targetPeriod));
    const uniqueAmounts = formattedAmounts.filter((amount, index) => (
      index === 0 || amount !== formattedAmounts[index - 1]
    ));
    const estimate = parsed.period !== targetPeriod;
    const prefix = formatCurrencyPrefix(parsed);
    const range = uniqueAmounts.length === 1
      ? `${prefix}${uniqueAmounts[0]}`
      : `${prefix}${uniqueAmounts[0]} - ${parsed.currencySymbol}${uniqueAmounts[1]}`;

    return {
      value: `${estimate ? '~' : ''}${range}/${targetPeriod === 'hour' ? 'hour' : 'year'}`,
      convertible: true,
      estimated: estimate,
      original,
      sourcePeriod: parsed.period,
      targetPeriod,
      hoursPerWeek: hours,
      weeksPerYear: WEEKS_PER_YEAR,
    };
  }

  function jobWithSalaryDisplay(job, mode = 'original', hoursPerWeek = DEFAULT_HOURS_PER_WEEK) {
    const source = job && typeof job === 'object' ? job : {};
    return {
      ...source,
      salary: convertSalary(source.salary, mode, hoursPerWeek).value,
    };
  }

  return {
    DEFAULT_HOURS_PER_WEEK,
    WEEKS_PER_YEAR,
    convertSalary,
    jobWithSalaryDisplay,
    normalizeHoursPerWeek,
    normalizeSalaryMode,
    parseSalary,
  };
}));
