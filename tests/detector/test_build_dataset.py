"""build_dataset: validation, dedup, group split by batch, test isolation and augmentation marking.

All records are neutral placeholders written to ``tmp_path`` (label 1 = contains the ``AAA`` token).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from mirsad.detector import normalize
from mirsad.detector.augment import (
    OBFUSCATIONS_BY_LANG,
    elongation,
    embed_in_carrier,
    homoglyphs,
    obfuscate,
    spacing_noise,
    tashkeel,
    zero_width,
)
from mirsad.detector.build_dataset import BuildConfig, build_dataset, is_test_batch, main
from mirsad.detector.dataset import CORE_SPLITS, DatasetRecord, read_records, text_hash

from .neutral_data import MARKER, make_records, record, write_batch

BAD_LINES = [
    "{not json",
    json.dumps({"id": "bad-missing-text", "label": 0, "lang": "en", "variety": "en", "carrier": "email",
                "attack_type": "none", "difficulty": "easy"}),
    json.dumps(record("bad-label", "a neutral line of text", 2, "en")),
    json.dumps(record("bad-lang", "a neutral line of text", 0, "en") | {"lang": "fr"}),
    json.dumps(record("al-0000", "different text reusing an existing id", 0, "en")),  # duplicate id
]


def write_dataset(root: Path) -> dict[str, list[dict]]:
    """A dataset with deliberate duplicates, conflicts, invalid lines and an external batch."""
    alpha = make_records("al", 30, lang="en", seed=1, serial_start=0)
    beta = make_records("be", 30, lang="ar", seed=2, serial_start=100)
    gamma = make_records("ga", 12, lang="mixed", seed=3, serial_start=200)
    test_en = make_records("tea", 10, lang="en", seed=4, serial_start=300)
    test_ar = make_records("tar", 10, lang="ar", seed=5, serial_start=400)
    test_mixed = make_records("tmx", 6, lang="mixed", seed=6, serial_start=500)
    ext_test = make_records("ext", 6, lang="en", seed=7, serial_start=600)
    ext_train = make_records("exr", 8, lang="en", seed=8, serial_start=700)

    # same text as al-0003 after normalisation (case + an invisible character) -> train duplicate
    variant = alpha[3]["text"].upper().replace(" ", " \u200b", 1)
    alpha.append(record("al-dup", variant, alpha[3]["label"], "en"))
    # exact copy of a test text inside a training batch -> the test copy must win
    beta.append(record("be-leak", test_ar[2]["text"], test_ar[2]["label"], "ar"))
    # the same text labelled 0 and 1 -> dropped everywhere
    conflict = "pallet ledger orchid conflict ref 999"
    alpha.append(record("al-conflict", conflict, 0, "en"))
    gamma.append(record("ga-conflict", conflict, 1, "mixed"))
    # a soft warning (kept): benign record carrying an attack type
    gamma.append(record("ga-warn", "timber canvas meadow violet ref 998 تقرير شحنة", 0, "mixed",
                        attack_type="goal_hijack"))

    write_batch(root / "raw" / "alpha.jsonl", alpha, extra_lines=BAD_LINES)
    write_batch(root / "raw" / "beta.jsonl", beta)
    write_batch(root / "raw" / "gamma.jsonl", gamma)
    write_batch(root / "raw" / "test-en-a.jsonl", test_en)
    write_batch(root / "raw" / "test-ar-a.jsonl", test_ar)
    write_batch(root / "raw" / "test-mixed-a.jsonl", test_mixed)
    write_batch(root / "external" / "test-Placeholder Set.jsonl", ext_test)
    write_batch(root / "external" / "extra.jsonl", ext_train)
    return {"alpha": alpha, "beta": beta, "gamma": gamma, "test_en": test_en, "test_ar": test_ar,
            "test_mixed": test_mixed, "ext_test": ext_test, "ext_train": ext_train}


@pytest.fixture()
def dataset(tmp_path: Path) -> tuple[Path, dict[str, list[dict]], dict]:
    root = tmp_path / "data"
    written = write_dataset(root)
    report = build_dataset(root, config=BuildConfig(seed=11))
    return root, written, report.stats


def load_splits(root: Path) -> dict[str, list[dict]]:
    return {p.stem: read_records(p) for p in sorted((root / "splits").glob("*.jsonl"))}


def base_id(rec_id: str) -> str:
    return rec_id.split("~")[0]


# --------------------------------------------------------------------------- outputs & validation


def test_split_files_and_stats_written(dataset):
    root, _, stats = dataset
    names = {p.stem for p in (root / "splits").glob("*.jsonl")}
    assert set(CORE_SPLITS) <= names
    assert "test_ext_placeholder_set" in names
    assert (root / "splits" / "stats.json").is_file()
    on_disk = json.loads((root / "splits" / "stats.json").read_text(encoding="utf-8"))
    assert on_disk["seed"] == 11
    assert set(on_disk["splits"]) == names
    for name, recs in load_splits(root).items():
        assert stats["splits"][name]["total"] == len(recs)
        for r in recs:
            DatasetRecord.model_validate({k: v for k, v in r.items() if k != "batch"})


def test_invalid_lines_are_reported_and_skipped(dataset):
    _, _, stats = dataset
    assert stats["invalid"]["count"] == len(BAD_LINES)
    wheres = [e["where"] for e in stats["invalid"]["examples"]]
    assert all(w.startswith("raw/alpha.jsonl:") for w in wheres)
    assert any("duplicate id" in e["error"] for e in stats["invalid"]["examples"])
    assert stats["warnings"]["by_type"].get("benign_with_attack_type") == 1
    files = {f["path"]: f for f in stats["inputs"]}
    assert files["raw/alpha.jsonl"]["invalid"] == len(BAD_LINES)
    assert files["raw/test-en-a.jsonl"]["test_batch"] is True


# --------------------------------------------------------------------------- group split & isolation


def test_test_batches_never_reach_train_or_val(dataset):
    root, written, stats = dataset
    splits = load_splits(root)
    test_names = [n for n in splits if n.startswith("test_")]
    test_ids = {r["id"] for n in test_names for r in splits[n]}
    test_hashes = {text_hash(r["text"]) for n in test_names for r in splits[n]}
    for name in ("train", "val"):
        for r in splits[name]:
            assert not is_test_batch(r["batch"]), r["id"]
            assert base_id(r["id"]) not in test_ids
            assert text_hash(r["text"]) not in test_hashes
    for name in test_names:
        assert all(is_test_batch(r["batch"]) for r in splits[name])
    assert stats["leakage_check"] == {"ok": True, "test_texts_in_train_val": 0, "test_ids_in_train_val": 0}
    # every test record is kept, in the split of its language
    assert {r["id"] for r in splits["test_en"]} == {r["id"] for r in written["test_en"]}
    assert {r["id"] for r in splits["test_ar"]} == {r["id"] for r in written["test_ar"]}
    assert {r["id"] for r in splits["test_mixed"]} == {r["id"] for r in written["test_mixed"]}
    assert {r["id"] for r in splits["test_ext_placeholder_set"]} == {r["id"] for r in written["ext_test"]}
    for lang in ("en", "ar", "mixed"):
        assert all(r["lang"] == lang for r in splits[f"test_{lang}"])


def test_batches_are_assigned_as_whole_groups(dataset):
    _, _, stats = dataset
    batches = stats["batches"]
    assert batches["alpha"] == ["train/val"]
    assert batches["extra"] == ["train/val"]
    assert batches["test-en-a"] == ["test_en"]
    assert batches["test-Placeholder Set"] == ["test_ext_placeholder_set"]


def test_train_val_split_is_stratified_and_complete(dataset):
    root, written, _ = dataset
    splits = load_splits(root)
    originals = [r for r in splits["train"] if "~aug-" not in r["id"]]
    pool_ids = {r["id"] for r in originals} | {r["id"] for r in splits["val"]}
    expected = {r["id"] for key in ("alpha", "beta", "gamma", "ext_train") for r in written[key]}
    expected -= {"al-dup", "be-leak", "al-conflict", "ga-conflict"}
    assert pool_ids == expected
    assert not ({r["id"] for r in originals} & {r["id"] for r in splits["val"]})
    for lang in ("en", "ar", "mixed"):
        labels = {r["label"] for r in splits["val"] if r["lang"] == lang}
        assert labels == {0, 1}, lang
    ext = [r for r in originals + splits["val"] if r["id"].startswith("exr-")]
    assert ext and all(r["source"] == "external/extra" for r in ext)


def test_record_soft_warnings_and_hard_validation():
    ok = DatasetRecord.model_validate(record("w-0", "pallet ledger orchid", 0, "en"))
    assert ok.warnings() == []
    assert DatasetRecord.model_validate(record("w-1", "pallet AAA", 1, "en", attack_type="none")).warnings() == [
        "injection_without_attack_type"]
    assert "lang_variety_mismatch" in DatasetRecord.model_validate(
        record("w-2", "pallet ledger", 0, "en", variety="gulf")).warnings()
    assert "lang_variety_mismatch" in DatasetRecord.model_validate(
        record("w-3", "تقرير شحنة", 0, "ar", variety="en")).warnings()
    assert DatasetRecord.model_validate(record("w-4", "pallet", 0, "en", reviewer="x")).warnings() == [
        "unknown_fields"]
    assert DatasetRecord.model_validate(record("  w-5  ", "pallet", 0, "en")).id == "w-5"
    for bad in (record("   ", "pallet", 0, "en"), record("w-6", "   ", 0, "en"), record("w-7", "x", True, "en")):
        with pytest.raises(ValueError):
            DatasetRecord.model_validate(bad)


# --------------------------------------------------------------------------- dedup


def test_dedup_normalised_duplicates_test_copies_win_and_conflicts_drop(dataset):
    root, written, stats = dataset
    splits = load_splits(root)
    all_ids = [base_id(r["id"]) for recs in splits.values() for r in recs]
    dups = stats["duplicates"]
    assert dups["removed"] == 2  # al-dup (normalised copy) + be-leak (copy of a test text)
    assert dups["cross_split_removed"] == 1
    assert dups["label_conflicts"] == 1
    assert sorted(dups["label_conflict_ids"]) == ["al-conflict", "ga-conflict"]
    assert "al-dup" not in all_ids and "al-0003" in all_ids
    assert "be-leak" not in all_ids
    assert written["test_ar"][2]["id"] in {r["id"] for r in splits["test_ar"]}
    assert "al-conflict" not in all_ids and "ga-conflict" not in all_ids
    originals = [r for name in splits for r in splits[name] if "~aug-" not in r["id"]]
    hashes = [text_hash(r["text"]) for r in originals]
    assert len(hashes) == len(set(hashes))


def test_text_hash_uses_normalised_text():
    assert text_hash("Pallet Ledger") == text_hash("pallet \u200bledger")
    assert text_hash("pallet ledger") != text_hash("pallet harbor")


# --------------------------------------------------------------------------- augmentation marking


def test_augmented_records_are_marked_and_train_only(dataset):
    root, _, stats = dataset
    splits = load_splits(root)
    aug = [r for r in splits["train"] if "~aug-" in r["id"]]
    assert aug, "augmentation should produce records with the default config"
    assert all(str(r["source"]).startswith("aug/") for r in aug)
    non_aug_sources = [r for r in splits["train"] if "~aug-" not in r["id"]]
    assert not any(str(r["source"]).startswith("aug/") for r in non_aug_sources)
    for name, recs in splits.items():
        if name != "train":
            assert not any("~aug-" in r["id"] or str(r.get("source", "")).startswith("aug/") for r in recs), name
    assert stats["splits"]["train"]["augmented"] == len(aug)
    assert sum(stats["augmentation"].values()) == len(aug)


def test_augmentation_preserves_labels(dataset):
    root, _, _ = dataset
    splits = load_splits(root)
    by_id = {r["id"]: r for r in splits["train"] if "~aug-" not in r["id"]}
    for r in (r for r in splits["train"] if "~aug-" in r["id"]):
        kind = r["source"]
        if kind.startswith("aug/embed-"):
            payload = by_id[r["notes"].split()[0].removeprefix("payload=")]
            assert r["label"] == 1 and payload["text"].strip() in r["text"]
        elif kind == "aug/concat-benign":
            assert r["label"] == 0 and MARKER not in r["text"]
        else:
            original = by_id[base_id(r["id"])]
            assert r["label"] == original["label"]
            if kind in ("aug/obf-zero_width", "aug/obf-homoglyphs", "aug/obf-tashkeel", "aug/obf-elongation"):
                assert normalize(r["text"]).text == normalize(original["text"]).text


def test_no_augment_option(tmp_path):
    root = tmp_path / "data"
    write_dataset(root)
    report = build_dataset(root, config=BuildConfig(seed=11, augment=False))
    train = read_records(root / "splits" / "train.jsonl")
    assert not any("~aug-" in r["id"] for r in train)
    assert report.stats["augmentation"] == {}


def test_build_is_deterministic(tmp_path):
    root = tmp_path / "data"
    write_dataset(root)
    build_dataset(root, config=BuildConfig(seed=5), out_dir=tmp_path / "a")
    build_dataset(root, config=BuildConfig(seed=5), out_dir=tmp_path / "b")
    for path in sorted((tmp_path / "a").glob("*.jsonl")):
        assert path.read_text(encoding="utf-8") == (tmp_path / "b" / path.name).read_text(encoding="utf-8")


def test_stale_external_test_splits_are_removed(tmp_path):
    root = tmp_path / "data"
    write_dataset(root)
    stale = root / "splits" / "test_ext_old.jsonl"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}\n", encoding="utf-8")
    build_dataset(root, config=BuildConfig(seed=1))
    assert not stale.exists()


def test_empty_data_dir_builds_empty_splits(tmp_path):
    report = build_dataset(tmp_path, config=BuildConfig(seed=1))
    assert all(s["total"] == 0 for s in report.splits.values())
    assert report.stats["leakage_check"]["ok"]


def test_cli_main(tmp_path, capsys):
    root = tmp_path / "data"
    write_dataset(root)
    assert main(["--data", str(root), "--seed", "3", "--val-fraction", "0.2"]) == 0
    out = capsys.readouterr().out
    assert "leakage check: OK" in out
    assert "test_ext_placeholder_set" in out
    assert json.loads((root / "splits" / "stats.json").read_text(encoding="utf-8"))["val_fraction"] == 0.2


# --------------------------------------------------------------------------- augment helpers on neutral text


EN = "Please review the quarterly invoice from the copper supplier before Thursday morning"
AR = "يرجى مراجعة فاتورة المورد الربعية قبل صباح يوم الخميس في المستودع الرئيسي"


@pytest.mark.parametrize("position", ["start", "middle", "end"])
def test_embed_in_carrier_positions(position):
    carrier = "First sentence here. Second sentence here. Third sentence here."
    out = embed_in_carrier(f"  {MARKER} note  ", carrier, position, random.Random(0))
    assert f"{MARKER} note" in out
    if position == "start":
        assert out.startswith(f"{MARKER} note")
    elif position == "end":
        assert out.endswith(f"{MARKER} note")
    else:
        assert out.startswith("First sentence here.") and out.endswith("Third sentence here.")
    with pytest.raises(ValueError):
        embed_in_carrier("p", carrier, "bottom", random.Random(0))


@pytest.mark.parametrize("seed", range(10))
def test_obfuscations_normalise_back(seed):
    for fn, text in ((zero_width, EN), (homoglyphs, EN), (zero_width, AR), (tashkeel, AR), (elongation, AR),
                     (homoglyphs, AR)):
        variant = fn(text, random.Random(seed))
        assert normalize(variant).text == normalize(text).text, fn.__name__


def test_obfuscations_change_the_text_and_spacing_noise_splits_words():
    rng = random.Random(1)
    for lang, text in (("en", EN), ("ar", AR)):
        for kind in OBFUSCATIONS_BY_LANG[lang]:
            assert obfuscate(text, kind, random.Random(1)) != text, kind
    spaced = spacing_noise(EN, rng)
    assert spaced.replace(" ", "") == EN.replace(" ", "")
    assert spacing_noise("a b c", rng) == "a b c"  # no word long enough
    with pytest.raises(ValueError):
        obfuscate(EN, "rot13", rng)
