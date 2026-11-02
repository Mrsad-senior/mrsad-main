"""Value extraction for taint tracking.

The tracker cannot follow bytes through an LLM, so it follows *recognisable values*
instead: e-mail addresses, URLs, domains, IBANs, phone numbers, long numbers, record IDs
and hashed word 8-grams of long free text. The same canonicalisation is applied to tool
results (sources) and to tool-call arguments (sinks), so a value matches regardless of
case, spacing, Arabic-Indic digits, invisible characters or URL encoding.
"""

from __future__ import annotations

import hashlib
import json
import re
import string
import unicodedata
from collections.abc import Iterable, Iterator, Mapping
from typing import Any, NamedTuple
from urllib.parse import unquote_plus

from mirsad.textutil import (
    EMAIL_RE,
    IBAN_RE,
    PHONE_RE,
    URL_RE,
    extract_domain,
    fold,
    split_addresses,
    strip_invisible,
)

NGRAM_SIZE = 8
VALUE_KINDS = ("email", "url", "domain", "iban", "phone", "number", "id", "ngram")

MAX_DEPTH = 64  # JSON nesting deeper than this is ignored (defends against recursion bombs)
MAX_LEAVES = 50_000  # leaves walked per structured value
MAX_TOKEN_LEN = 64  # longest string treated as a single ID token

_DIGIT_FOLD = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٬٫", "01234567890123456789,.")
# Length-preserving upper-casing: str.upper() can change length ("ß" -> "SS"), breaking spans.
_ASCII_UPPER = str.maketrans(string.ascii_lowercase, string.ascii_uppercase)
_URL_TRAILING = ".,;:!?'\"،؛)]}>…"
_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_HOST_RE = re.compile(r"^[^\s/@:?#\\]+\.[^\s/@:?#\\.]+$")

NUMBER_RE = re.compile(r"(?<![\d,])\d{1,3}(?:,\d{3})+(?![\d,])|(?<!\d)\d{6,}(?!\d)")
ID_RE = re.compile(r"(?<![A-Za-z0-9_\-])[A-Z]{1,6}-?\d{2,}(?![A-Za-z0-9_\-])")
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]*")
_WORD_RE = re.compile(r"\w+")
_SAUDI_MOBILE_RE = re.compile(r"(?:00966|966|0)?(5\d{8})")
# ISO 13616 IBAN lengths for the region and common counterparties (others: 15..34 accepted).
IBAN_LENGTHS = {
    "SA": 24, "AE": 23, "BH": 22, "KW": 30, "QA": 29, "OM": 23, "JO": 30, "EG": 29, "LB": 28,
    "TR": 26, "GB": 22, "DE": 22, "FR": 27, "IT": 27, "ES": 24, "NL": 18, "CH": 21, "BE": 16,
}  # fmt: skip


class ExtractedValue(NamedTuple):
    """One value found in a tool result: ``(value, kind, field_path, from_trusted_field)``."""

    value: str
    kind: str
    field: str | None
    trusted_field: bool


class ArgCandidate(NamedTuple):
    """A value found inside a tool-call argument, ready to be looked up in the taint index."""

    param: str  # argument path, e.g. "body" or "message.to[0]"
    kind: str
    value: str  # canonical form
    excerpt: str  # human-readable text for evidence (the n-gram words for kind "ngram")


class DestinationItem(NamedTuple):
    """One destination (recipient, URL, IBAN, ...) named by a destination argument."""

    param: str
    raw: str
    kind: str
    value: str
    domain: str | None


# --------------------------------------------------------------------------- canonical forms


def prepare(text: str) -> str:
    """NFKC, invisible characters removed, Arabic-Indic digits and separators to ASCII.

    Unlike :func:`mirsad.textutil.fold` this keeps letter case, which the IBAN and ID
    patterns rely on.
    """
    text = unicodedata.normalize("NFKC", text)
    text, _ = strip_invisible(text)
    return text.translate(_DIGIT_FOLD)


def canonical_email(raw: str) -> str:
    local, _, domain = raw.strip().strip("<>\"'").lower().rpartition("@")
    return f"{local.strip('.')}@{domain.strip('.')}"


def canonical_url(raw: str) -> str | None:
    url = raw.strip().rstrip(_URL_TRAILING).lower().rstrip("/")
    scheme, sep, rest = url.partition("://")
    if not sep or not scheme.startswith("http") or not rest:
        return None
    return url


def canonical_domain(raw: str | None) -> str | None:
    if not raw:
        return None
    domain = raw.strip().lower().rstrip(".")
    if domain.startswith("www."):
        domain = domain[4:]
    if len(domain) > 253 or not (_HOST_RE.match(domain) or _IPV4_RE.match(domain)):
        return None
    return domain


def domain_suffixes(domain: str) -> list[str]:
    """``a.b.evil.example`` -> [``a.b.evil.example``, ``b.evil.example``, ``evil.example``]."""
    if _IPV4_RE.match(domain):
        return [domain]
    labels = domain.split(".")
    return [".".join(labels[i:]) for i in range(max(1, len(labels) - 1))]


def canonical_phone(raw: str) -> str:
    """E.164-style form; Saudi mobiles in any notation (05.., 5.., 9665.., +966 5..) agree."""
    digits = re.sub(r"\D", "", raw)
    match = _SAUDI_MOBILE_RE.fullmatch(digits)
    if match:
        return "+966" + match.group(1)
    if digits.startswith("00"):
        digits = digits[2:]
    return "+" + digits


def canonical_iban(raw: str) -> str | None:
    tokens = [t for t in re.split(r"[\s.-]+", raw) if t]
    # Matching on upper-cased text can swallow a following word ("... 7519 please").
    while len(tokens) > 1 and tokens[-1].isalpha():
        tokens.pop()
    iban = "".join(tokens).upper()
    expected = IBAN_LENGTHS.get(iban[:2])
    if expected and len(iban) > expected:
        iban = iban[:expected]
    if not 15 <= len(iban) <= 34:
        return None
    bban = iban[4:]
    # Real BBANs are mostly digits; this rejects look-alikes such as "FY24 PLAN WILL HAVE".
    if sum(c.isdigit() for c in bban) * 2 < len(bban):
        return None
    return iban


def canonical_id(raw: str) -> str:
    return raw.strip().upper()


def _overlaps(span: tuple[int, int], taken: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < t_end and t_start < end for t_start, t_end in taken)


def atomic_values(text: str) -> Iterator[tuple[str, str]]:
    """Yield ``(canonical_value, kind)`` for every non-n-gram value in already-prepared text."""
    for m in URL_RE.finditer(text):
        url = canonical_url(m.group(0))
        if url:
            yield url, "url"
            domain = canonical_domain(extract_domain(url))
            if domain:
                yield domain, "domain"
    for m in EMAIL_RE.finditer(text):
        email = canonical_email(m.group(0))
        yield email, "email"
        domain = canonical_domain(email.rpartition("@")[2])
        if domain:
            yield domain, "domain"
    # Numeric-looking kinds can overlap; claim spans in priority order IBAN > ID > phone > number.
    taken: list[tuple[int, int]] = []
    for m in IBAN_RE.finditer(text.translate(_ASCII_UPPER)):
        iban = canonical_iban(m.group(0))
        if iban:
            taken.append(m.span())
            yield iban, "iban"
    for m in ID_RE.finditer(text):
        if not _overlaps(m.span(), taken):
            taken.append(m.span())
            yield canonical_id(m.group(0)), "id"
    for m in PHONE_RE.finditer(text):
        if not _overlaps(m.span(), taken):
            taken.append(m.span())
            yield canonical_phone(m.group(0)), "phone"
    for m in NUMBER_RE.finditer(text):
        if _overlaps(m.span(), taken):
            continue
        digits = re.sub(r"\D", "", m.group(0))
        if len(digits) >= 6:
            taken.append(m.span())
            yield digits, "number"


# --------------------------------------------------------------------------- n-grams


def ngram_tokens(text: str) -> list[str]:
    """Word tokens of the folded text (Arabic-normalised, lower case, ASCII digits)."""
    return _WORD_RE.findall(fold(text))


def ngram_hash(words: Iterable[str]) -> str:
    return hashlib.blake2b(" ".join(words).encode("utf-8"), digest_size=8).hexdigest()


def iter_ngrams(text: str, *, size: int = NGRAM_SIZE, stride: int = 1) -> Iterator[tuple[str, str]]:
    """Yield ``(hash, window_text)`` for word ``size``-grams; the last window is always included."""
    tokens = ngram_tokens(text)
    if len(tokens) < size:
        return
    last = len(tokens) - size
    starts = list(range(0, last + 1, max(1, stride)))
    if starts[-1] != last:
        starts.append(last)
    for i in starts:
        window = tokens[i : i + size]
        yield ngram_hash(window), " ".join(window)


# --------------------------------------------------------------------------- structured walking


class _TrustedFields:
    """Matches a field path against ``trusted_fields`` (plain keys or dotted path suffixes)."""

    def __init__(self, fields: Iterable[str]) -> None:
        cleaned = [f.strip().lower() for f in fields if f and f.strip()]
        self.keys = frozenset(f for f in cleaned if "." not in f)
        self.paths = tuple(f for f in cleaned if "." in f)

    def matches(self, key: str, norm_path: str) -> bool:
        if key.lower() in self.keys:
            return True
        return any(norm_path == p or norm_path.endswith("." + p) for p in self.paths)


class _Leaf(NamedTuple):
    path: str | None
    text: str
    trusted: bool
    key: str | None


def _maybe_json(text: str) -> Any | None:
    stripped = text.strip()
    if not stripped or stripped[0] not in "{[":
        return None
    try:
        parsed = json.loads(stripped)
    except (ValueError, RecursionError):
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def _iter_leaves(data: Any, trusted: _TrustedFields) -> Iterator[_Leaf]:
    count = 0

    def walk(
        value: Any, path: str, norm: str, is_trusted: bool, key: str | None, depth: int
    ) -> Iterator[_Leaf]:
        nonlocal count
        if depth > MAX_DEPTH or count >= MAX_LEAVES:
            return
        if isinstance(value, Mapping):
            for k, v in value.items():
                k = str(k)
                child = f"{path}.{k}" if path else k
                child_norm = f"{norm}.{k.lower()}" if norm else k.lower()
                yield from walk(
                    v, child, child_norm, is_trusted or trusted.matches(k, child_norm), k, depth + 1
                )
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                yield from walk(v, f"{path}[{i}]", norm, is_trusted, key, depth + 1)
        elif isinstance(value, str) or (isinstance(value, (int, float)) and not isinstance(value, bool)):
            count += 1
            yield _Leaf(path or None, str(value), is_trusted, key)

    yield from walk(data, "", "", False, None, 0)


def _is_id_key(key: str) -> bool:
    lower = key.lower()
    return lower == "id" or lower.endswith(("_id", "-id")) or (len(key) > 2 and key.endswith("Id"))


def _id_from_key(text: str) -> str | None:
    """Whole value of an ``*_id`` field, when it looks like an opaque identifier."""
    token = text.strip()
    if not 3 <= len(token) <= MAX_TOKEN_LEN or any(c.isspace() for c in token):
        return None
    if not any(c.isdigit() for c in token) or token.isdigit():
        return None  # words ("inbox") are not identifiers; long pure numbers are kind "number"
    return canonical_id(token)


def extract_values(
    text_or_structured: Any,
    *,
    trusted_fields: Iterable[str],
    ngram_size: int = NGRAM_SIZE,
    ngram_stride: int = 1,
    include_ngrams: bool = True,
) -> list[ExtractedValue]:
    """Extract taint-relevant values from a tool result.

    Accepts plain text, a JSON string, or parsed JSON (dicts/lists). For structured data the
    dotted field path is kept (``emails[0].from``) and ``from_trusted_field`` is set when the
    leaf key, or any key above it, is listed in ``trusted_fields``. Free text contributes
    hashed word n-grams (``ngram_size`` words, every ``ngram_stride`` words) when it has at
    least ``ngram_size`` words. Values are returned in canonical form, de-duplicated, in
    document order.
    """
    data = text_or_structured
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8", "replace")
    if isinstance(data, str):
        parsed = _maybe_json(data)
        if parsed is not None:
            data = parsed
    if data is None:
        return []

    matcher = _TrustedFields(trusted_fields)
    out: dict[tuple[str, str, str | None, bool], ExtractedValue] = {}

    def add(value: str, kind: str, leaf: _Leaf) -> None:
        item = ExtractedValue(value, kind, leaf.path, leaf.trusted)
        out.setdefault((value, kind, leaf.path, leaf.trusted), item)

    for leaf in _iter_leaves(data, matcher):
        prepared = prepare(leaf.text)
        for value, kind in atomic_values(prepared):
            add(value, kind, leaf)
        if leaf.key is not None and _is_id_key(leaf.key):
            ident = _id_from_key(prepared)
            if ident:
                add(ident, "id", leaf)
        if include_ngrams:
            for digest, _ in iter_ngrams(leaf.text, size=ngram_size, stride=ngram_stride):
                add(digest, "ngram", leaf)
    return list(out.values())


# --------------------------------------------------------------------------- arguments (sinks)


def _iter_arg_strings(value: Any, path: str, depth: int = 0) -> Iterator[tuple[str, str]]:
    if depth > MAX_DEPTH:
        return
    if isinstance(value, Mapping):
        for k, v in value.items():
            yield from _iter_arg_strings(v, f"{path}.{k}" if path else str(k), depth + 1)
    elif isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value, key=repr) if isinstance(value, (set, frozenset)) else value
        for i, v in enumerate(items):
            yield from _iter_arg_strings(v, f"{path}[{i}]", depth + 1)
    elif isinstance(value, str):
        yield path, value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield path, str(value)


def _text_variants(text: str) -> list[str]:
    """The text itself plus its URL-decoded form (data smuggled in a query string)."""
    variants = [text]
    if "%" in text or "+" in text:
        decoded = unquote_plus(text)
        if decoded != text:
            variants.append(decoded)
    return variants


def argument_candidates(arguments: Mapping[str, Any], *, ngram_size: int = NGRAM_SIZE) -> list[ArgCandidate]:
    """Every value embedded anywhere in the call arguments (all n-gram windows, stride 1)."""
    out: dict[tuple[str, str, str], ArgCandidate] = {}

    def add(param: str, kind: str, value: str, excerpt: str) -> None:
        out.setdefault((param, kind, value), ArgCandidate(param, kind, value, excerpt))

    for param, text in _iter_arg_strings(arguments, ""):
        for variant in _text_variants(text):
            prepared = prepare(variant)
            for value, kind in atomic_values(prepared):
                add(param, kind, value, value)
            # Arguments are matched case-insensitively against IDs (results use the strict pattern).
            for token in _TOKEN_RE.findall(prepared):
                if 3 <= len(token) <= MAX_TOKEN_LEN and any(c.isdigit() for c in token):
                    add(param, "id", canonical_id(token), token)
            for digest, window in iter_ngrams(variant, size=ngram_size, stride=1):
                add(param, "ngram", digest, window)
    return list(out.values())


def _iter_dest_strings(value: Any, depth: int = 0) -> Iterator[str]:
    if value is None or depth > MAX_DEPTH:
        return
    if isinstance(value, Mapping):
        for v in value.values():
            yield from _iter_dest_strings(v, depth + 1)
    elif isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value, key=repr) if isinstance(value, (set, frozenset)) else value
        for v in items:
            yield from _iter_dest_strings(v, depth + 1)
    elif not isinstance(value, bool):
        yield str(value)


def destination_items(param: str, value: Any) -> list[DestinationItem]:
    """Split a destination argument (address list, URL, IBAN, ...) into individual destinations."""
    items: dict[tuple[str, str], DestinationItem] = {}

    def add(raw: str, kind: str, canon: str, domain: str | None) -> None:
        items.setdefault((kind, canon), DestinationItem(param, raw, kind, canon, domain))

    for text in _iter_dest_strings(value):
        prepared = prepare(text).strip()
        if not prepared:
            continue
        found = False
        url_spans: list[tuple[int, int]] = []
        for m in URL_RE.finditer(prepared):
            url = canonical_url(m.group(0))
            if url:
                url_spans.append(m.span())
                add(m.group(0), "url", url, canonical_domain(extract_domain(url)))
                found = True
        for m in EMAIL_RE.finditer(prepared):
            if _overlaps(m.span(), url_spans):
                continue  # an address inside a URL query is data, not the destination
            email = canonical_email(m.group(0))
            add(m.group(0), "email", email, canonical_domain(email.rpartition("@")[2]))
            found = True
        taken: list[tuple[int, int]] = list(url_spans)
        for m in IBAN_RE.finditer(prepared.translate(_ASCII_UPPER)):
            iban = canonical_iban(m.group(0))
            if iban and not _overlaps(m.span(), taken):
                taken.append(m.span())
                add(m.group(0), "iban", iban, None)
                found = True
        for m in PHONE_RE.finditer(prepared):
            if not _overlaps(m.span(), taken):
                taken.append(m.span())
                add(m.group(0), "phone", canonical_phone(m.group(0)), None)
                found = True
        if found:
            continue
        for token in split_addresses(prepared):
            token = token.strip("<>\"'()[]")
            if not token:
                continue
            host = token.split("/", 1)[0] if "/" in token else token
            domain = canonical_domain(host)
            if domain and "/" not in token:
                add(token, "domain", domain, domain)
            else:
                add(token, "id", canonical_id(token), domain)
    return list(items.values())
