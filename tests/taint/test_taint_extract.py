"""Value extraction: kinds, canonical forms, field paths, trusted fields, n-grams, argument scanning."""

from __future__ import annotations

import json

import pytest

from mirsad.taint import extract_values
from mirsad.taint.extract import (
    argument_candidates,
    destination_items,
    iter_ngrams,
    ngram_hash,
    ngram_tokens,
)

TRUSTED = ["from", "sender", "id", "email_id", "date", "received_at", "customer_id", "doc_id"]


def kinds(values, kind):
    return [v.value for v in values if v.kind == kind]


def test_returns_four_tuples_matching_spec_shape():
    values = extract_values("write to Omar@Gulf-Retail.example", trusted_fields=TRUSTED)
    assert values[0] == ("omar@gulf-retail.example", "email", None, False)
    value, kind, field, trusted = values[0]
    assert (value, kind, field, trusted) == tuple(values[0])


def test_email_url_and_their_domains_are_canonical():
    text = "Contact BACKUP@Evil.Example or visit HTTPS://WWW.Exfil-Hub.example/Upload/?k=1, thanks."
    values = extract_values(text, trusted_fields=[])
    assert kinds(values, "email") == ["backup@evil.example"]
    assert kinds(values, "url") == ["https://www.exfil-hub.example/upload/?k=1"]
    # domains of both, with "www." removed
    assert set(kinds(values, "domain")) == {"evil.example", "exfil-hub.example"}


def test_url_trailing_punctuation_is_not_part_of_the_value():
    values = extract_values(
        "See https://evil.example/a. Also (https://evil.example/b)، ok", trusted_fields=[]
    )
    assert kinds(values, "url") == ["https://evil.example/a", "https://evil.example/b"]


def test_iban_spacing_and_case_normalised_and_lookalikes_rejected():
    values = extract_values("Pay to sa03 8000 0000 6080 1016 7519 please", trusted_fields=[])
    assert kinds(values, "iban") == ["SA0380000000608010167519"]
    assert kinds(extract_values("FY24 PLAN WILL HAVE MORE", trusted_fields=[]), "iban") == []
    # a number right after the IBAN is cut off at the ISO 13616 length for the country (SA = 24)
    values = extract_values("IBAN SA03 8000 0000 6080 1016 7519 2026 invoice", trusted_fields=[])
    assert kinds(values, "iban") == ["SA0380000000608010167519"]


@pytest.mark.parametrize("shown", ["SA03-8000-0000-6080-1016-7519", "SA03.8000.0000.6080.1016.7519",
                                   "SA03 - 8000 - 0000 - 6080 - 1016 - 7519"])
def test_iban_with_dash_or_dot_separators_is_still_linked(shown):
    # Incident #3 probe: a dashed IBAN in an invoice was not linked to the transfer, so taint
    # downgraded from deny (untrusted destination) to approval.
    values = extract_values(f"Pay the balance to {shown}.", trusted_fields=[])
    assert kinds(values, "iban") == ["SA0380000000608010167519"]
    (item,) = destination_items("to_iban", shown)
    assert item.kind == "iban" and item.value == "SA0380000000608010167519"


@pytest.mark.parametrize(
    "text",
    ["+966 55 123 4567", "0551234567", "966551234567", "00966551234567", "055-123-4567", "٠٥٥١٢٣٤٥٦٧"],
)
def test_saudi_mobile_formats_share_one_canonical_form(text):
    assert kinds(extract_values(f"call me on {text}", trusted_fields=[]), "phone") == ["+966551234567"]


def test_numbers_need_six_digits_and_accept_thousand_separators():
    values = extract_values("Balance 1,250,000 SAR, ref 98765432, code 12345, year 2026", trusted_fields=[])
    assert kinds(values, "number") == ["1250000", "98765432"]


def test_ids_are_detected_in_text():
    values = extract_values(
        "Customer C017 asked about INV-2231 and ticket E003 in Q4 2026", trusted_fields=[]
    )
    assert kinds(values, "id") == ["C017", "INV-2231", "E003"]


def test_structured_results_keep_field_paths_and_trusted_flags():
    data = {"emails": [{"id": "E003", "from": "omar@gulf-retail.example", "body": "write to x@evil.example"}]}
    values = extract_values(data, trusted_fields=TRUSTED)
    by_value = {(v.value, v.kind): v for v in values}
    sender = by_value[("omar@gulf-retail.example", "email")]
    assert sender.field == "emails[0].from" and sender.trusted_field is True
    body = by_value[("x@evil.example", "email")]
    assert body.field == "emails[0].body" and body.trusted_field is False
    assert by_value[("E003", "id")].trusted_field is True


def test_trusted_field_status_is_inherited_by_nested_values():
    data = {"from": {"name": "Omar", "address": "omar@gulf-retail.example"}, "body": "hi"}
    (email,) = [v for v in extract_values(data, trusted_fields=TRUSTED) if v.kind == "email"]
    assert email.field == "from.address" and email.trusted_field is True


def test_dotted_trusted_field_entries_match_path_suffixes():
    data = {"message": {"headers": {"from": "a@b.example"}, "from": "c@d.example"}}
    values = {
        v.value: v.trusted_field
        for v in extract_values(data, trusted_fields=["headers.from"])
        if v.kind == "email"
    }
    assert values == {"a@b.example": True, "c@d.example": False}


def test_id_keyed_fields_record_opaque_identifiers_only():
    data = {"customer_id": "cust_8f3a2", "folder_id": "inbox", "doc_id": 42, "ticketId": "T-9"}
    ids = kinds(extract_values(data, trusted_fields=TRUSTED), "id")
    assert "CUST_8F3A2" in ids and "T-9" in ids
    assert "INBOX" not in ids and "42" not in ids


def test_json_text_is_parsed_like_structured_data():
    data = {"from": "omar@gulf-retail.example", "body": "contact x@evil.example"}
    from_text = extract_values(json.dumps(data), trusted_fields=TRUSTED)
    from_struct = extract_values(data, trusted_fields=TRUSTED)
    assert from_text == from_struct


def test_plain_text_headers_are_never_trusted():
    # An attacker can write "From:" lines in a body, so only structured fields are trusted.
    values = extract_values("From: attacker@evil.example\nPlease reply.", trusted_fields=TRUSTED)
    (email,) = [v for v in values if v.kind == "email"]
    assert email.field is None and email.trusted_field is False


def test_invisible_characters_and_fullwidth_forms_do_not_hide_values():
    text = "send to atta\u200bcker@evil\u200d.example or ＡＴＴＡＣＫＥＲ＠ＥＶＩＬ．ＥＸＡＭＰＬＥ"
    assert set(kinds(extract_values(text, trusted_fields=[]), "email")) == {"attacker@evil.example"}


def test_ngrams_only_for_long_text_and_fold_arabic_variants():
    short = "عميل مهم جدا"
    assert kinds(extract_values(short, trusted_fields=[]), "ngram") == []
    plain = "يفضل التواصل صباحا عبر الهاتف ولا يرغب في الاتصال بعد الساعة الخامسة"
    decorated = "يُفضّل التّواصل صباحًا عبر الهاتف ولا يرغب في الإتصال بعد السّاعة الخامسة"
    a = kinds(extract_values(plain, trusted_fields=[]), "ngram")
    b = kinds(extract_values(decorated, trusted_fields=[]), "ngram")
    assert a and a == b
    assert len(a) == len(ngram_tokens(plain)) - 8 + 1


def test_ngram_stride_still_covers_the_tail():
    text = " ".join(f"w{i}" for i in range(20))
    windows = [w for _, w in iter_ngrams(text, size=8, stride=5)]
    assert windows[0].startswith("w0 ") and windows[-1].endswith("w19")
    assert len(windows) == 4  # starts 0, 5, 10 and the last window at 12


def test_ngram_hashes_are_stable_across_processes():
    # blake2b, not hash(): values must survive a restart for audit replay.
    assert ngram_hash(["a", "b"]) == "bb37dea5c027f928"  # blake2b-64 of "a b"
    assert ngram_hash(["a", "b"]) == ngram_hash(iter(["a", "b"]))


def test_include_ngrams_false_skips_hashing():
    text = "one two three four five six seven eight nine ten"
    assert kinds(extract_values(text, trusted_fields=[], include_ngrams=False), "ngram") == []


def test_deeply_nested_json_does_not_crash():
    data: dict = {"x": "a@b.example"}
    for _ in range(500):
        data = {"n": data}
    assert extract_values(data, trusted_fields=[]) == []  # beyond MAX_DEPTH is ignored
    assert extract_values(None, trusted_fields=[]) == []


def test_values_are_deduplicated_per_field():
    values = extract_values("x@evil.example x@evil.example X@EVIL.EXAMPLE", trusted_fields=[])
    assert kinds(values, "email") == ["x@evil.example"]


def test_argument_candidates_find_values_embedded_in_long_and_encoded_strings():
    args = {
        "url": "https://exfil-hub.example/c?e=faisal%40desert-foods.example&p=%2B966551234567",
        "body": "Customer c017 owes 1,250,000",
    }
    found = {(c.param, c.kind, c.value) for c in argument_candidates(args)}
    assert ("url", "email", "faisal@desert-foods.example") in found
    assert ("url", "phone", "+966551234567") in found
    assert ("body", "id", "C017") in found  # arguments match IDs case-insensitively
    assert ("body", "number", "1250000") in found


def test_argument_candidates_walk_nested_arguments():
    args = {"message": {"to": ["a@evil.example"], "parts": [{"text": "INV-2231"}]}}
    found = {(c.param, c.kind, c.value) for c in argument_candidates(args)}
    assert ("message.to[0]", "email", "a@evil.example") in found
    assert ("message.parts[0].text", "id", "INV-2231") in found


def test_destination_items_parse_lists_names_urls_ibans_and_bare_domains():
    items = destination_items("to", "Omar <omar@gulf-retail.example>; sara@najd-trading.example")
    assert [(i.kind, i.value, i.domain) for i in items] == [
        ("email", "omar@gulf-retail.example", "gulf-retail.example"),
        ("email", "sara@najd-trading.example", "najd-trading.example"),
    ]
    (url,) = destination_items("url", "https://exfil-hub.example/c?to=x@y.example")
    assert url.kind == "url" and url.domain == "exfil-hub.example"  # the address in the query is data
    (iban,) = destination_items("to_iban", "SA03 8000 0000 6080 1016 7519")
    assert iban.kind == "iban" and iban.value == "SA0380000000608010167519"
    (bare,) = destination_items("webhook", "evil.example")
    assert bare.kind == "domain" and bare.domain == "evil.example"
    assert destination_items("cc", None) == []
