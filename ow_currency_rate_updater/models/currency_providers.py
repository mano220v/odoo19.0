# -*- coding: utf-8 -*-
"""
Lightweight, dependency-free fetchers for live currency exchange rates.

Every fetcher returns a tuple: (rates_dict, meta_dict)
    rates_dict: {currency_code: rate}  where rate = units of that currency
                per 1 unit of `base_currency` (this matches the convention
                used by Odoo's res.currency.rate.rate field when the base
                currency is the company currency).
    meta_dict:  {'source_date': str or None, 'provider_label': str}

All fetchers raise CurrencyProviderError on any failure, with a clear,
user-facing message - never a raw traceback.
"""
import json
import logging
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)

TIMEOUT = 15  # seconds


class CurrencyProviderError(Exception):
    """Raised whenever a provider cannot be reached or returns bad data."""
    pass


def _http_get_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {'User-Agent': 'Odoo-Wings-Currency-Updater/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raise CurrencyProviderError("The rate provider returned HTTP %s (%s)" % (e.code, e.reason))
    except urllib.error.URLError as e:
        raise CurrencyProviderError("Could not reach the rate provider: %s" % (e.reason,))
    except Exception as e:  # noqa: BLE001
        raise CurrencyProviderError("Unexpected error contacting the rate provider: %s" % (e,))
    try:
        return json.loads(raw.decode('utf-8'))
    except Exception:  # noqa: BLE001
        raise CurrencyProviderError("The rate provider did not return valid JSON.")


def _http_get_text(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {'User-Agent': 'Odoo-Wings-Currency-Updater/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        raise CurrencyProviderError("The rate provider returned HTTP %s (%s)" % (e.code, e.reason))
    except urllib.error.URLError as e:
        raise CurrencyProviderError("Could not reach the rate provider: %s" % (e.reason,))
    except Exception as e:  # noqa: BLE001
        raise CurrencyProviderError("Unexpected error contacting the rate provider: %s" % (e,))


def fetch_frankfurter(base_currency):
    """Frankfurter.app - free, no API key, ECB-sourced, supports any base currency."""
    url = "https://api.frankfurter.app/latest?from=%s" % base_currency
    data = _http_get_json(url)
    rates = data.get('rates') or {}
    if not rates:
        raise CurrencyProviderError("Frankfurter returned no rates for base currency %s." % base_currency)
    rates[base_currency] = 1.0
    return rates, {'source_date': data.get('date'), 'provider_label': 'Frankfurter.app (ECB data)'}


def fetch_ecb(base_currency):
    """European Central Bank daily reference rates - official XML feed, EUR-based.
    Cross-rates to another base currency are computed from the EUR figures.
    """
    url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
    xml_text = _http_get_text(url)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        raise CurrencyProviderError("Could not parse the ECB rate feed (invalid XML).")

    ns = {'ecb': 'http://www.ecb.int/vocabulary/2002-08-01/eurofxref'}
    cube_time = root.find('.//ecb:Cube[@time]', ns)
    source_date = cube_time.get('time') if cube_time is not None else None

    eur_rates = {'EUR': 1.0}
    for cube in root.findall('.//ecb:Cube[@currency]', ns):
        code = cube.get('currency')
        rate = cube.get('rate')
        if code and rate:
            eur_rates[code] = float(rate)

    if len(eur_rates) <= 1:
        raise CurrencyProviderError("The ECB feed did not contain any currency rates.")

    if base_currency not in eur_rates:
        raise CurrencyProviderError(
            "ECB does not publish a rate for %s, so it can't be used as the base currency "
            "with this provider. Try Frankfurter or a custom API instead." % base_currency
        )

    base_to_eur = eur_rates[base_currency]
    rates = {code: (rate / base_to_eur) for code, rate in eur_rates.items()}
    rates[base_currency] = 1.0
    return rates, {'source_date': source_date, 'provider_label': 'European Central Bank (official)'}


def fetch_custom(url, api_key, base_currency):
    """Any JSON API exposing a top-level {"rates": {"CODE": number, ...}} object
    (this covers most free/paid providers: exchangerate-api.com, open.er-api.com,
    Fixer-style APIs, etc). An optional API key is sent both as a Bearer header
    and as an `apikey` query hint for broad compatibility.
    """
    if not url:
        raise CurrencyProviderError("No custom API URL is configured.")
    headers = {'User-Agent': 'Odoo-Wings-Currency-Updater/1.0'}
    if api_key:
        headers['Authorization'] = 'Bearer %s' % api_key
        headers['apikey'] = api_key
    data = _http_get_json(url, headers=headers)
    rates = data.get('rates') or data.get('conversion_rates') or {}
    if not rates:
        raise CurrencyProviderError(
            "The custom API response didn't contain a 'rates' (or 'conversion_rates') object. "
            "Point this at an endpoint shaped like {\"rates\": {\"USD\": 1.08, ...}}."
        )
    rates = {code: float(val) for code, val in rates.items()}
    rates.setdefault(base_currency, 1.0)
    return rates, {
        'source_date': data.get('date') or data.get('time_last_update_utc'),
        'provider_label': 'Custom API',
    }


PROVIDERS = {
    'frankfurter': fetch_frankfurter,
    'ecb': fetch_ecb,
}


def fetch_rates(provider, base_currency, custom_url=None, custom_api_key=None):
    """Dispatch to the right provider fetcher. Returns (rates, meta)."""
    if provider == 'custom':
        return fetch_custom(custom_url, custom_api_key, base_currency)
    fn = PROVIDERS.get(provider)
    if not fn:
        raise CurrencyProviderError("Unknown rate provider: %s" % provider)
    return fn(base_currency)
