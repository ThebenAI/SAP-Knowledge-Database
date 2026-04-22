from __future__ import annotations

from html import unescape
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.models.sap_module_lookup_cache import SapModuleLookupCache

SAP_MODULES: tuple[str, ...] = (
    "FI",
    "CO",
    "MM",
    "SD",
    "PP",
    "WM",
    "EWM",
    "HCM",
    "PM",
    "QM",
    "Basis",
    "Cross-Module",
)

LOCAL_TABLE_MODULE_MAP: dict[str, str] = {
    "EKKO": "MM",
    "EKPO": "MM",
    "MARA": "MM",
    "MARC": "MM",
    "MAKT": "MM",
    "VBAK": "SD",
    "VBAP": "SD",
    "BKPF": "FI",
    "BSEG": "FI",
}

SAP_ONLY_LOOKUP_URLS: tuple[str, ...] = (
    "https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/{table_name}",
    "https://help.sap.com/http.svc/search?q={table_name}",
    "https://api.sap.com/search?query={table_name}",
)

MODULE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bmaterials?\s+management\b", re.IGNORECASE), "MM"),
    (re.compile(r"\bsales\s+and\s+distribution\b", re.IGNORECASE), "SD"),
    (re.compile(r"\bfinancial\s+accounting\b", re.IGNORECASE), "FI"),
    (re.compile(r"\bcontrolling\b", re.IGNORECASE), "CO"),
    (re.compile(r"\bproduction\s+planning\b", re.IGNORECASE), "PP"),
    (re.compile(r"\bwarehouse\s+management\b", re.IGNORECASE), "WM"),
    (re.compile(r"\bextended\s+warehouse\s+management\b", re.IGNORECASE), "EWM"),
    (re.compile(r"\bhuman\s+capital\s+management\b", re.IGNORECASE), "HCM"),
    (re.compile(r"\bplant\s+maintenance\b", re.IGNORECASE), "PM"),
    (re.compile(r"\bquality\s+management\b", re.IGNORECASE), "QM"),
    (re.compile(r"\bbasis\b", re.IGNORECASE), "Basis"),
)


def _sanitize_table_name(table_name: str | None) -> str:
    if not table_name:
        return ""
    return table_name.strip().upper()


def _strip_html(text: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", text)
    normalized = re.sub(r"\s+", " ", no_tags)
    return unescape(normalized).strip()


def _extract_module_from_text(text: str) -> str | None:
    for pattern, module in MODULE_PATTERNS:
        if pattern.search(text):
            return module
    return None


def _lookup_module_from_sap_web(table_name: str) -> str | None:
    encoded = quote(table_name)
    headers = {"User-Agent": "SAP-Knowledge-Tool/1.0"}
    for url_tpl in SAP_ONLY_LOOKUP_URLS:
        url = url_tpl.format(table_name=encoded)
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=3) as resp:
                if resp.status != 200:
                    continue
                body = resp.read(200_000).decode("utf-8", errors="ignore")
        except (HTTPError, URLError, TimeoutError):
            continue
        text = _strip_html(body)
        module = _extract_module_from_text(text)
        if module:
            return module
    return None


def suggest_sap_module_for_table_local_only(table_name: str | None) -> tuple[str | None, str | None]:
    normalized = _sanitize_table_name(table_name)
    if not normalized:
        return None, None

    local = LOCAL_TABLE_MODULE_MAP.get(normalized)
    if local:
        return local, "local"
    return None, None


def suggest_sap_module_for_table(
    table_name: str | None,
    *,
    db: Session | None = None,
    run_cache: dict[str, tuple[str | None, str | None]] | None = None,
) -> tuple[str | None, str | None]:
    normalized = _sanitize_table_name(table_name)
    if not normalized:
        return None, None

    if run_cache is not None and normalized in run_cache:
        return run_cache[normalized]

    local, source = suggest_sap_module_for_table_local_only(normalized)
    if local:
        result = (local, source)
        if run_cache is not None:
            run_cache[normalized] = result
        return result

    # Persistent cache lookup (includes previous "not found" lookups with source=None).
    if db is not None:
        cached = db.query(SapModuleLookupCache).filter(SapModuleLookupCache.table_name == normalized).first()
        if cached is not None:
            result = (cached.sap_module, cached.source)
            if run_cache is not None:
                run_cache[normalized] = result
            return result

    web = _lookup_module_from_sap_web(normalized)
    if web:
        result = (web, "web")
    else:
        result = (None, None)

    if db is not None:
        cached = db.query(SapModuleLookupCache).filter(SapModuleLookupCache.table_name == normalized).first()
        if cached is None:
            cached = SapModuleLookupCache(table_name=normalized)
        cached.sap_module = result[0]
        cached.source = result[1]
        db.add(cached)

    if run_cache is not None:
        run_cache[normalized] = result
    return result
