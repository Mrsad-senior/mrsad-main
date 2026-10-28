from __future__ import annotations

import base64
import hashlib
import json
import time

import jwt
import pytest

from mirsad import auth
from mirsad.auth import (
    AgentInfo,
    AlreadyExistsError,
    AuthError,
    LoginThrottle,
    NotFoundError,
    UserInfo,
    authenticate_agent_key,
    authenticate_user,
    create_agent,
    create_token,
    create_user,
    decode_token,
    delete_agent,
    delete_user,
    generate_agent_key,
    get_agent,
    get_user,
    hash_agent_key,
    hash_password,
    list_agents,
    list_users,
    needs_rehash,
    parse_agent_key,
    rotate_agent_key,
    update_agent,
    update_user,
    user_from_token,
    verify_password,
)
from mirsad.storage import AgentRow, UserRow

SECRET = "jwt-test-secret-0123456789abcdef0123456789abcdef"


# ----------------------------------------------------------------------------- passwords


def test_password_hash_round_trip_and_format():
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$scrypt$ln=14,r=8,p=1$")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("correct horse battery stapler", hashed)
    assert not needs_rehash(hashed)


def test_password_hash_is_salted():
    a, b = hash_password("same-password"), hash_password("same-password")
    assert a != b and verify_password("same-password", a) and verify_password("same-password", b)


def test_password_unicode_arabic():
    hashed = hash_password("كلمة-سر-قوية-٢٠٢٤")
    assert verify_password("كلمة-سر-قوية-٢٠٢٤", hashed)
    assert not verify_password("كلمة-سر-قوية-2024", hashed)


@pytest.mark.parametrize("bad", [
    "", "plaintext", "$argon2id$v=19$m=65536$abc$def", "$scrypt$ln=14,r=8$c2FsdA$aGFzaA",
    "$scrypt$ln=30,r=8,p=1$c2FsdHNhbHRzYWx0$" + "A" * 43,  # absurd cost: rejected, not computed
    "$scrypt$ln=14,r=8,p=1$!!!$###",
])
def test_verify_password_rejects_malformed_hashes(bad):
    assert verify_password("anything", bad) is False


def test_needs_rehash_for_weaker_parameters():
    salt = b"0123456789abcdef"
    digest = hashlib.scrypt(b"pw-123456", salt=salt, n=2**10, r=8, p=1, dklen=32)
    weak = f"$scrypt$ln=10,r=8,p=1${base64.b64encode(salt).decode().rstrip('=')}$" \
           f"{base64.b64encode(digest).decode().rstrip('=')}"
    assert verify_password("pw-123456", weak)
    assert needs_rehash(weak) and needs_rehash("garbage")


def test_hash_password_rejects_empty():
    with pytest.raises(ValueError):
        hash_password("")


# ----------------------------------------------------------------------------- JWT


def test_token_round_trip_claims():
    token = create_token("noura", "approver", SECRET, ttl_hours=2)
    claims = decode_token(token, SECRET)
    assert claims["sub"] == "noura" and claims["role"] == "approver" and claims["iss"] == "mirsad"
    assert claims["exp"] - claims["iat"] == 7200
    assert abs(claims["iat"] - time.time()) < 5 and claims["jti"]
    assert jwt.get_unverified_header(token)["alg"] == "HS256"


def test_expired_token_rejected():
    now = int(time.time())
    token = jwt.encode({"sub": "noura", "role": "admin", "iat": now - 7200, "exp": now - 3600, "iss": "mirsad"},
                       SECRET, algorithm="HS256")
    with pytest.raises(AuthError, match="expired"):
        decode_token(token, SECRET)


def test_wrong_secret_and_tampered_payload_rejected():
    token = create_token("noura", "auditor", SECRET, ttl_hours=1)
    with pytest.raises(AuthError):
        decode_token(token, "another-secret-0123456789abcdef0123456789")
    header, payload, sig = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["role"] = "admin"
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    with pytest.raises(AuthError):
        decode_token(f"{header}.{forged}.{sig}", SECRET)


def test_alg_none_and_missing_claims_rejected():
    unsigned = jwt.encode({"sub": "noura", "role": "admin", "iat": 1, "exp": 2**31, "iss": "mirsad"}, None,
                          algorithm="none")
    with pytest.raises(AuthError):
        decode_token(unsigned, SECRET)
    no_role = jwt.encode({"sub": "noura", "iat": int(time.time()), "exp": int(time.time()) + 60, "iss": "mirsad"},
                         SECRET, algorithm="HS256")
    with pytest.raises(AuthError):
        decode_token(no_role, SECRET)
    bad_role = jwt.encode({"sub": "n", "role": "root", "iat": int(time.time()), "exp": int(time.time()) + 60,
                           "iss": "mirsad"}, SECRET, algorithm="HS256")
    with pytest.raises(AuthError):
        decode_token(bad_role, SECRET)
    with pytest.raises(AuthError):
        decode_token("", SECRET)


def test_create_token_validates_arguments():
    with pytest.raises(ValueError):
        create_token("noura", "root", SECRET, 1)
    with pytest.raises(ValueError):
        create_token("noura", "admin", "", 1)
    with pytest.raises(ValueError):
        create_token("noura", "admin", SECRET, 0)


# ----------------------------------------------------------------------------- agent keys


def test_generate_agent_key_format():
    key, prefix, digest = generate_agent_key()
    assert key.startswith(f"mk_{prefix}_") and len(prefix) == 8 and prefix.isalnum() and prefix.islower()
    assert len(key.split("_", 2)[2]) >= 32
    assert digest == hash_agent_key(key) == hashlib.sha256(key.encode()).hexdigest()
    assert parse_agent_key(key) == prefix
    assert generate_agent_key()[0] != key


@pytest.mark.parametrize("bad", ["", "mk_short_x", "sk_abcdefgh_" + "a" * 40, "mk_ABCDEFGH_" + "a" * 40,
                                 "mk_abcdefgh_" + "a" * 10, "mk_abcdefgh_" + "a!" * 20])
def test_parse_agent_key_rejects_malformed(bad):
    assert parse_agent_key(bad) is None


def test_agent_create_authenticate_and_last_seen(db):
    info, key = create_agent(db, "email-crm", "Email & CRM Assistant", "email-crm-assistant", "reads mail")
    assert info == AgentInfo(id="email-crm", name="Email & CRM Assistant", policy_agent_id="email-crm-assistant")
    with db.session() as sess:
        row = sess.get(AgentRow, "email-crm")
        assert row.key_hash == hash_agent_key(key) and key not in (row.key_hash, row.key_prefix)
        assert row.last_seen_at is None
    assert authenticate_agent_key(db, key) == info
    assert authenticate_agent_key(db, f"  {key}  ") == info
    assert get_agent(db, "email-crm").last_seen_at is not None


def test_agent_wrong_or_unknown_key_rejected(db):
    _, key = create_agent(db, "email-crm", "Email & CRM Assistant", "email-crm-assistant")
    prefix = parse_agent_key(key)
    assert authenticate_agent_key(db, f"mk_{prefix}_{'x' * 43}") is None   # right prefix, wrong secret
    assert authenticate_agent_key(db, generate_agent_key()[0]) is None     # unknown prefix
    assert authenticate_agent_key(db, "not-a-key") is None


def test_disabled_agent_rejected(db):
    _, key = create_agent(db, "email-crm", "Email & CRM Assistant", "email-crm-assistant")
    update_agent(db, "email-crm", disabled=True)
    assert authenticate_agent_key(db, key) is None
    update_agent(db, "email-crm", disabled=False)
    assert authenticate_agent_key(db, key) is not None


def test_rotate_agent_key_invalidates_old_key(db):
    _, old = create_agent(db, "email-crm", "Email & CRM Assistant", "email-crm-assistant")
    new = rotate_agent_key(db, "email-crm")
    assert new != old
    assert authenticate_agent_key(db, old) is None
    assert authenticate_agent_key(db, new).id == "email-crm"
    with pytest.raises(NotFoundError):
        rotate_agent_key(db, "ghost")


def test_agent_validation_duplicates_and_crud(db):
    with pytest.raises(ValueError):
        create_agent(db, "Bad Id!", "x", "y")
    create_agent(db, "finance-bot", "Finance Bot", "finance")
    with pytest.raises(AlreadyExistsError):
        create_agent(db, "finance-bot", "Finance Bot", "finance")
    updated = update_agent(db, "finance-bot", name="Finance Assistant", policy_agent_id="finance-v2")
    assert updated.name == "Finance Assistant" and updated.policy_agent_id == "finance-v2"
    assert [a.id for a in list_agents(db)] == ["finance-bot"]
    assert "key_hash" not in list_agents(db)[0].model_dump()
    assert delete_agent(db, "finance-bot") and not delete_agent(db, "finance-bot")
    with pytest.raises(NotFoundError):
        update_agent(db, "finance-bot", name="x")


def test_prefix_collision_still_authenticates_the_right_agent(db, monkeypatch):
    real = auth.generate_agent_key
    keys = iter(["mk_samepref_" + "a" * 43, "mk_samepref_" + "b" * 43])

    def fixed():
        key = next(keys)
        return key, "samepref", hash_agent_key(key)

    monkeypatch.setattr(auth, "generate_agent_key", fixed)
    _, key_a = create_agent(db, "agent-a", "A", "a")
    _, key_b = create_agent(db, "agent-b", "B", "b")
    monkeypatch.setattr(auth, "generate_agent_key", real)
    assert authenticate_agent_key(db, key_a).id == "agent-a"
    assert authenticate_agent_key(db, key_b).id == "agent-b"


# ----------------------------------------------------------------------------- users


def test_user_create_and_authenticate(db):
    info = create_user(db, "noura", "Str0ng-Passw0rd", "approver", display_name="نورة", lang="ar")
    assert info == UserInfo(username="noura", role="approver", display_name="نورة", lang="ar")
    assert authenticate_user(db, "noura", "Str0ng-Passw0rd") == info
    assert authenticate_user(db, "noura", "wrong-password") is None
    assert authenticate_user(db, "nobody", "Str0ng-Passw0rd") is None
    with db.session() as sess:
        stored = sess.query(UserRow).filter_by(username="noura").one().password_hash
    assert "Str0ng-Passw0rd" not in stored and stored.startswith("$scrypt$")


def test_disabled_user_cannot_log_in_or_use_token(db):
    create_user(db, "bader", "Str0ng-Passw0rd", "auditor")
    token = create_token("bader", "auditor", SECRET, 1)
    assert user_from_token(db, token, SECRET).username == "bader"
    update_user(db, "bader", disabled=True)
    assert authenticate_user(db, "bader", "Str0ng-Passw0rd") is None
    with pytest.raises(AuthError):
        user_from_token(db, token, SECRET)


def test_user_from_token_reflects_current_role(db):
    create_user(db, "sara", "Str0ng-Passw0rd", "approver")
    token = create_token("sara", "approver", SECRET, 1)
    update_user(db, "sara", role="admin")
    assert user_from_token(db, token, SECRET).role == "admin"
    delete_user(db, "sara")
    with pytest.raises(AuthError):
        user_from_token(db, token, SECRET)


@pytest.mark.parametrize(("username", "password", "role", "lang"), [
    ("ab", "Str0ng-Passw0rd", "admin", "en"),          # username too short
    ("bad user", "Str0ng-Passw0rd", "admin", "en"),    # space
    ("noura", "short", "admin", "en"),                 # password too short
    ("noura", "Str0ng-Passw0rd", "root", "en"),        # unknown role
    ("noura", "Str0ng-Passw0rd", "admin", "fr"),       # unsupported language
])
def test_create_user_validation(db, username, password, role, lang):
    with pytest.raises(ValueError):
        create_user(db, username, password, role, lang=lang)


def test_duplicate_user_and_user_crud(db):
    create_user(db, "noura", "Str0ng-Passw0rd", "admin")
    with pytest.raises(AlreadyExistsError):
        create_user(db, "noura", "An0ther-Passw0rd", "auditor")
    update_user(db, "noura", password="N3w-Passw0rd!", display_name="Noura A.", lang="ar")
    assert authenticate_user(db, "noura", "Str0ng-Passw0rd") is None
    assert authenticate_user(db, "noura", "N3w-Passw0rd!").lang == "ar"
    details = get_user(db, "noura")
    assert details.display_name == "Noura A." and "password_hash" not in details.model_dump()
    assert [u.username for u in list_users(db)] == ["noura"]
    with pytest.raises(ValueError):
        update_user(db, "noura", role="root")
    with pytest.raises(NotFoundError):
        update_user(db, "ghost", lang="en")
    assert delete_user(db, "noura") and get_user(db, "noura") is None


# ----------------------------------------------------------------------------- throttle


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_throttle_blocks_after_five_failures_within_window():
    clock = FakeClock()
    throttle = LoginThrottle(clock=clock)
    for i in range(4):
        assert throttle.record_failure("noura", "10.0.0.1") == i + 1
        assert not throttle.is_blocked("noura", "10.0.0.1")
    throttle.record_failure("Noura", "10.0.0.1")  # usernames are case-insensitive
    assert throttle.is_blocked("noura", "10.0.0.1")
    assert throttle.retry_after("noura", "10.0.0.1") == pytest.approx(300)
    clock.now += 120
    assert throttle.retry_after("noura", "10.0.0.1") == pytest.approx(180)


def test_throttle_window_slides_and_unblocks():
    clock = FakeClock()
    throttle = LoginThrottle(clock=clock)
    for _ in range(5):
        throttle.record_failure("noura", "10.0.0.1")
        clock.now += 10
    assert throttle.is_blocked("noura", "10.0.0.1")
    clock.now = 1000 + 300  # exactly 5 minutes after the first failure (t=1000): it leaves the window
    assert not throttle.is_blocked("noura", "10.0.0.1")
    assert throttle.failures("noura", "10.0.0.1") == 4


def test_throttle_is_per_username_and_ip_and_resets():
    throttle = LoginThrottle(clock=FakeClock())
    for _ in range(5):
        throttle.record_failure("noura", "10.0.0.1")
    assert throttle.is_blocked("noura", "10.0.0.1")
    assert not throttle.is_blocked("noura", "10.0.0.2")
    assert not throttle.is_blocked("bader", "10.0.0.1")
    throttle.reset("noura", "10.0.0.1")
    assert not throttle.is_blocked("noura", "10.0.0.1") and throttle.retry_after("noura", "10.0.0.1") == 0


def test_throttle_memory_is_bounded():
    throttle = LoginThrottle(max_keys=100, clock=FakeClock())
    for i in range(1_000):
        throttle.record_failure(f"user{i}", "10.0.0.1")
    assert len(throttle._failures) == 100
    with pytest.raises(ValueError):
        LoginThrottle(max_failures=0)
