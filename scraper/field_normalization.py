"""Conservative display cleanup for extracted tracker fields."""

import re


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
        return text

    amount = text[prefix.end():].strip(' :|-\u2013\u2014')
    if not amount or not _SALARY_AMOUNT_RE.search(amount):
        return ''
    return amount
