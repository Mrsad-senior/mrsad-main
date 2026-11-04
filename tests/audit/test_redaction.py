from __future__ import annotations

import copy

import pytest

from mirsad.audit import REDACTED, is_secret_key, luhn_valid, redact, redact_text
from mirsad.models import Action, ToolCall

# Every secret below is synthetic test data.
SECRETS = [
    ("openai key", "use sk-proj-AbCdEf0123456789GhIjKlMnOp for the call", "AbCdEf0123456789"),
    ("anthropic key", "key=sk-ant-api03-AbCdEf0123456789GhIjKl_mn", "AbCdEf0123456789"),
    ("stripe key", "sk_live_51HabcdefGHIJKLmnopQRST", "51HabcdefGHIJ"),
    ("mirsad agent key", "X-Mirsad-Key: mk_ab12cd34_Zx9_Yw8-Vu7Ts6Rq5Po4Nm3Lk2Jh1Gf0Ed", "Zx9_Yw8-Vu7Ts6"),
    ("aws access key", "AKIAIOSFODNN7EXAMPLE is the id", "AKIAIOSFODNN7EXAMPLE"),
    ("github token", "token ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789", "ghp_AbCdEfGhIj"),
    ("github pat", "github_pat_11ABCDEFG0123456789_abcdefghijklmnop", "11ABCDEFG0123456789"),
    ("slack token", "xoxb-1234567890-0987654321-AbCdEfGhIjKl", "1234567890-0987654321"),
    ("google key", "AIzaSyA1234567890abcdefghijklmnopqrstuv", "AIzaSyA1234567890"),
    ("jwt", "cookie eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJub3VyYSJ9.dGhpcy1pcy1hLXNpZw", "eyJzdWIiOiJub3VyYSJ9"),
    ("bearer header", "Authorization: Bearer 9f8e7d6c5b4a39281706f5e4d3c2b1a0", "9f8e7d6c5b4a3928"),
    ("basic header", "authorization: Basic bm91cmE6c2VjcmV0cGFzcw==", "bm91cmE6c2VjcmV0cGFzcw"),
    ("bearer in prose", "send it with bearer abc123.def456-ghi789xyz", "abc123.def456"),
    ("pem key", "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\nIBAAK\n-----END RSA PRIVATE KEY-----", "MIIEow"),
    ("openssh key", "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjE\n-----END OPENSSH PRIVATE KEY-----",
     "b3BlbnNzaC1rZXktdjE"),
    ("truncated pem", "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC", "MIIEvQIBADAN"),
    ("password assignment", "login with password=Hunter2Hunter2 now", "Hunter2Hunter2"),
    ("json password in text", '{"password": "Tr0ub4dor&3"}', "Tr0ub4dor"),
    ("api_key assignment", "api_key: 'zyx987wvu654'", "zyx987wvu654"),
    ("client secret", "client-secret = s3cr3tValue99", "s3cr3tValue99"),
    ("url token", "https://files.najd-trading.example/dl?token=abcd1234efgh", "abcd1234efgh"),
    ("arabic password", "كلمة المرور: Najd@2024", "Najd@2024"),
]


@pytest.mark.parametrize(("name", "text", "secret"), SECRETS, ids=[s[0] for s in SECRETS])
def test_secret_shapes_are_removed(name, text, secret):
    out = redact_text(text)
    assert secret not in out, out
    assert "REDACTED" in out


NORMAL = [
    "Please send the Q3 invoice to ahmed@najd-trading.example by Sunday.",
    "مرحباً، أرجو إرسال عرض السعر للعميل قبل نهاية الأسبوع.",
    "Order 12345 totals 4,500 SAR; call 0551234567 or +966 55 123 4567.",
    "Visit https://www.najd-trading.example/catalog?page=2&sort=price",
    "A basic understanding of bearer bonds is useful; the token economy grew.",
    "The task-force reviewed the risk-free plan on 2024-01-15 and 2024-02-16.",
    "Timestamp 1760198400.123 and build 20240115.",
    "Use the secret ingredient: love.",
    "Invoice INV-2024-000123 for customer C017.",
]


@pytest.mark.parametrize("text", NORMAL)
def test_normal_text_is_untouched(text):
    assert redact_text(text) == text


def test_luhn_valid_card_masked_to_last_four():
    assert redact_text("card 4111 1111 1111 1111 ok") == "card **** **** **** 1111 ok"
    assert redact_text("pan 5555555555554444.") == "pan ************4444."
    assert redact_text("amex 3782-822463-10005") == "amex ****-******-*0005"


def test_luhn_invalid_number_is_not_masked():
    assert not luhn_valid("4111111111111112")
    assert redact_text("ref 4111111111111112") == "ref 4111111111111112"


def test_arabic_indic_card_digits_masked():
    out = redact_text("البطاقة ٤١١١١١١١١١١١١١١١")
    assert out.endswith("١١١١") and "*" * 12 in out


def test_saudi_national_id_and_iqama_masked_to_last_four():
    assert redact_text("هوية 1012345678") == "هوية ******5678"
    assert redact_text("Iqama: 2234567890.") == "Iqama: ******7890."
    assert redact_text("id ١٠١٢٣٤٥٦٧٨") == "id ******٥٦٧٨"


def test_national_id_rules_skip_other_numbers():
    assert redact_text("phone 0512345678") == "phone 0512345678"       # starts with 0
    assert redact_text("big 30123456789") == "big 30123456789"         # 11 digits
    assert redact_text("float 1760198400.5") == "float 1760198400.5"   # decimal number


def test_iban_masked_except_country_and_last_four():
    assert redact_text("IBAN SA03 8000 0000 6080 1016 7519") == "IBAN SA** **** **** **** **** 7519"
    assert redact_text("to SA0380000000608010167519 now") == "to SA" + "*" * 18 + "7519 now"


def test_dashed_and_dotted_ibans_are_masked_too():
    # Found during incident #3: separators other than spaces left the IBAN in the audit log in clear.
    assert redact_text("IBAN SA03-8000-0000-6080-1016-7519.") == "IBAN SA**-****-****-****-****-7519."
    assert redact_text("IBAN SA03.8000.0000.6080.1016.7519") == "IBAN SA**.****.****.****.****.7519"


def test_secret_keys_redacted_in_nested_structures():
    data = {
        "user": "noura",
        "password": "hunter2hunter2",
        "headers": {"Authorization": "Basic Zm9vOmJhcg==", "X-Api-Key": "abc", "Accept": "json"},
        "items": [{"accessToken": "t0k3n"}, {"client_secret": "cs"}],
        "keys": {"p256dh": "BKey", "auth": "authsecret"},
        "token_type": "bearer",
        "max_tokens": 512,
        "author": "Bader",
    }
    out = redact(data)
    assert out["password"] == REDACTED
    assert out["headers"]["Authorization"] == REDACTED and out["headers"]["X-Api-Key"] == REDACTED
    assert out["headers"]["Accept"] == "json"
    assert out["items"] == [{"accessToken": REDACTED}, {"client_secret": REDACTED}]
    assert out["keys"]["auth"] == REDACTED
    assert out["token_type"] == "bearer" and out["max_tokens"] == 512 and out["author"] == "Bader"


@pytest.mark.parametrize(("key", "secret"), [
    ("password", True), ("PASSWORD", True), ("db_password", True), ("passwordHash", True), ("apiKey", True),
    ("x-api-key", True), ("refresh_token", True), ("Cookie", True), ("pin", True), ("cvv", True),
    ("token_count", False), ("max_tokens", False), ("author", False), ("key_prefix", False),
    ("spinner", False), ("tokens", False), ("secretary", False),
])
def test_is_secret_key(key, secret):
    assert is_secret_key(key) is secret


def test_national_id_field_masked_even_as_integer():
    out = redact({"national_id": 1012345678, "iqama": "2234567890", "ts": 1760198400})
    assert out == {"national_id": "******5678", "iqama": "******7890", "ts": 1760198400}


def test_integer_card_number_masked():
    assert redact({"n": 4111111111111111}) == {"n": "************1111"}
    assert redact({"n": 1760198400123}) == {"n": 1760198400123}  # ms timestamp untouched


def test_redact_does_not_mutate_input_and_converts_models():
    data = {"password": "x" * 10, "nested": {"text": "id 1012345678"}}
    original = copy.deepcopy(data)
    redact(data)
    assert data == original
    call = ToolCall(session_id="s", agent_id="a", tool="send_email",
                    arguments={"to": "x@najd-trading.example", "api_key": "k-123"})
    out = redact({"call": call, "action": Action.DENY, "tags": ("a", "b"), "raw": b"\x00\x01"})
    assert out["call"]["arguments"]["api_key"] == REDACTED
    assert out["call"]["arguments"]["to"] == "x@najd-trading.example"
    assert out["action"] == "deny" and out["tags"] == ["a", "b"] and out["raw"] == "base64:AAE="


def test_scalars_and_empty_values_pass_through():
    assert redact(None) is None
    assert redact(3.5) == 3.5
    assert redact({"password": ""}) == {"password": ""}
    assert redact({"password": None}) == {"password": None}
    assert redact(float("nan")) == "nan"
