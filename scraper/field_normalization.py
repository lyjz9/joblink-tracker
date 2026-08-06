"""Conservative display cleanup for extracted tracker fields."""

import re
from decimal import Decimal, InvalidOperation


_LOCATION_ACRONYMS = frozenset({
    'AK', 'AL', 'AR', 'AS', 'AZ', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL',
    'GA', 'GU', 'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'MA',
    'MD', 'ME', 'MI', 'MN', 'MO', 'MP', 'MS', 'MT', 'NC', 'ND', 'NE',
    'NH', 'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'PR', 'RI',
    'SC', 'SD', 'TN', 'TX', 'UT', 'VA', 'VI', 'VT', 'WA', 'WI', 'WV',
    'WY',
    'AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC',
    'SK', 'YT',
    'ACT', 'APAC', 'EMEA', 'EU', 'LATAM', 'NSW', 'NYC', 'QLD', 'SA',
    'TAS', 'UAE', 'UK', 'US', 'USA', 'VIC',
})
_LOCATION_CONNECTORS = frozenset({'AND', 'OF', 'THE'})
_LOCATION_WORD_RE = re.compile(r"[^\W\d_]+(?:['\u2019][^\W\d_]+)*", re.UNICODE)
_SALARY_PREFIX_RE = re.compile(
    r'^\s*(?:the\s+)?'
    r'(?:(?:estimated|expected|annual|annualized|hourly|starting|total)\s+)*'
    r'(?:base\s+)?'
    r'(?:salary|pay|compensation|wage|rate)'
    r'(?:\s+(?:range|rate))?'
    r'\s*(?:(?:is|of)\s+|[:|\-\u2013\u2014]\s*)?',
    re.IGNORECASE,
)
_SALARY_AMOUNT_RE = re.compile(
    r'(?:[$\u00a3\u20ac\u00a5\u20b9]\s*\d)'
    r'|(?:\b(?:USD|CAD|AUD|GBP|EUR|JPY|INR)\s*\$?\s*\d)'
    r'|(?:\b\d[\d,.]*\s*[kK]\b)'
    r'|(?:\b\d[\d,.]*\s*(?:/|per\s+|an?\s+)(?:hour|hr|year|yr|week|wk)\b)'
    r'|(?:\b\d{2,3}(?:,\d{3})+(?:\.\d+)?\b)'
    r'|(?:\b\d[\d,.]*\s*(?:-|\u2013|\u2014|to)\s*\d[\d,.]*\b)',
    re.IGNORECASE,
)
_EQUAL_SALARY_RANGE_RE = re.compile(
    r'^(?P<left_currency>'
    r'(?:(?:USD|CAD|AUD|GBP|EUR|JPY|INR)\s*[$\u00a3\u20ac\u00a5\u20b9]?'
    r'|[$\u00a3\u20ac\u00a5\u20b9])\s*)?'
    r'(?P<left_amount>\d+(?:,\d{3})*(?:\.\d+)?)'
    r'(?P<left_scale>\s*[kK])?'
    r'(?P<left_unit>\s*(?:(?:per\s+|/\s*|an?\s+)'
    r'(?:year|yr|hour|hr|annum|week|wk)))?'
    r'\s*(?:-|\u2013|\u2014|\bto\b|\band\b)\s*'
    r'(?P<right_currency>'
    r'(?:(?:USD|CAD|AUD|GBP|EUR|JPY|INR)\s*[$\u00a3\u20ac\u00a5\u20b9]?'
    r'|[$\u00a3\u20ac\u00a5\u20b9])\s*)?'
    r'(?P<right_amount>\d+(?:,\d{3})*(?:\.\d+)?)'
    r'(?P<right_scale>\s*[kK])?'
    r'(?P<right_unit>\s*(?:(?:per\s+|/\s*|an?\s+)'
    r'(?:year|yr|hour|hr|annum|week|wk)))?'
    r'(?P<trailing>\s*(?:\([^)]*\))?\s*)$',
    re.IGNORECASE,
)
_CURRENCY_ALIASES = {
    '$': '$',
    '\u00a3': 'GBP',
    '\u20ac': 'EUR',
    '\u00a5': 'JPY',
    '\u20b9': 'INR',
}

_MISSING_DISPLAY_VALUES = frozenset({'', 'n/a', 'na', 'none', 'null'})


def normalize_location_display(value):
    """Title-case all-caps places without lowercasing location abbreviations."""
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    letters = ''.join(character for character in text if character.isalpha())
    if not letters or not letters.isupper():
        return text

    word_index = 0

    def replace_word(match):
        nonlocal word_index
        word = match.group(0)
        upper = word.upper()
        if upper in _LOCATION_ACRONYMS:
            cleaned = upper
        elif word_index and upper in _LOCATION_CONNECTORS:
            cleaned = upper.lower()
        elif upper.startswith('MC') and len(upper) > 3 and "'" not in word:
            cleaned = f"Mc{upper[2:].capitalize()}"
        else:
            cleaned = word.title()
        word_index += 1
        return cleaned

    return _LOCATION_WORD_RE.sub(replace_word, text)


def normalize_salary_display(value):
    """Remove a leading salary label while preserving the quoted amount and unit."""
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    if not text:
        return ''

    prefix = _SALARY_PREFIX_RE.match(text)
    if not prefix:
        return _collapse_equal_salary_range(text)

    amount = text[prefix.end():].strip(' :|-\u2013\u2014')
    if not amount or not _SALARY_AMOUNT_RE.search(amount):
        return ''
    return _collapse_equal_salary_range(amount)


def default_unspecified_work_type(value, result):
    """Default a complete, successful posting to Onsite when work type is absent."""
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    if text.lower() not in _MISSING_DISPLAY_VALUES:
        return text
    if result.get('error'):
        return 'n/a'
    if any(
        str(result.get(field) or '').strip().lower() in _MISSING_DISPLAY_VALUES
        for field in ('company', 'job_title', 'location')
    ):
        return 'n/a'
    return 'Onsite'


def _collapse_equal_salary_range(value):
    match = _EQUAL_SALARY_RANGE_RE.fullmatch(value)
    if not match:
        return value

    try:
        left_amount = Decimal(match.group('left_amount').replace(',', ''))
        right_amount = Decimal(match.group('right_amount').replace(',', ''))
    except InvalidOperation:
        return value
    if left_amount != right_amount:
        return value

    left_scale = (match.group('left_scale') or '').strip().lower()
    right_scale = (match.group('right_scale') or '').strip().lower()
    if left_scale != right_scale:
        return value

    left_currency = _currency_key(match.group('left_currency'))
    right_currency = _currency_key(match.group('right_currency'))
    if not _compatible_salary_parts(left_currency, right_currency, dollar_codes={'USD', 'CAD', 'AUD'}):
        return value

    left_unit = _unit_key(match.group('left_unit'))
    right_unit = _unit_key(match.group('right_unit'))
    if not _compatible_salary_parts(left_unit, right_unit):
        return value

    currency = re.sub(
        r'\s+',
        ' ',
        (match.group('left_currency') or match.group('right_currency') or '').strip(),
    )
    amount = match.group('left_amount')
    scale = (match.group('left_scale') or match.group('right_scale') or '').strip()
    unit = re.sub(
        r'\s+',
        ' ',
        (match.group('left_unit') or match.group('right_unit') or '').strip(),
    )
    trailing = (match.group('trailing') or '').strip()

    if currency and currency[-1].isalpha():
        collapsed = f'{currency} {amount}{scale}'
    else:
        collapsed = f'{currency}{amount}{scale}'
    collapsed += unit if unit.startswith('/') else f' {unit}' if unit else ''
    collapsed += f' {trailing}' if trailing else ''
    return collapsed


def _currency_key(value):
    compact = re.sub(r'\s+', '', str(value or '')).upper()
    if not compact:
        return ''
    for code in ('USD', 'CAD', 'AUD', 'GBP', 'EUR', 'JPY', 'INR'):
        if compact.startswith(code):
            return code
    return _CURRENCY_ALIASES.get(compact, compact)


def _unit_key(value):
    match = re.search(
        r'\b(year|yr|annum|hour|hr|week|wk)\b',
        str(value or ''),
        flags=re.IGNORECASE,
    )
    if not match:
        return ''
    return {
        'yr': 'year',
        'annum': 'year',
        'hr': 'hour',
        'wk': 'week',
    }.get(match.group(1).lower(), match.group(1).lower())


def _compatible_salary_parts(left, right, dollar_codes=None):
    if not left or not right or left == right:
        return True
    dollar_codes = dollar_codes or set()
    return '$' in {left, right} and ({left, right} - {'$'}).issubset(dollar_codes)
