"""Build detector train / val / test splits from ``raw/`` and ``external/`` JSONL batches.

    python -m mirsad.detector.build_dataset --data data/detector

* every line is validated against :class:`~mirsad.detector.dataset.DatasetRecord`; bad lines are
  reported (file, line, reason) and skipped;
* duplicates are removed by the hash of the detector-normalised text (test copies win, so a text that
  also appears in a test batch never reaches train/val); texts labelled both 0 and 1 are dropped;
* group split: batches named ``test-*`` only feed test splits (``test_en`` / ``test_ar`` / ``test_mixed``
  by language; external ``test-<name>`` batches become ``test_ext_<name>``); all other batches are split
  85/15 into train/val, stratified by (label, lang) with a fixed seed;
* augmentation (train only, ``source = aug/...``): positives embedded in benign carriers at start /
  middle / end, benign carrier concatenations (so length is not a shortcut), and obfuscation variants
  (zero-width, homoglyphs, tashkeel, spacing noise, Arabic elongation).
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from mirsad.detector.augment import OBFUSCATIONS_BY_LANG, embed_in_carrier, obfuscate
from mirsad.detector.dataset import CORE_SPLITS, DatasetRecord, iter_jsonl, text_hash, write_jsonl

log = logging.getLogger("mirsad.detector")

DEFAULT_SEED = 1337
MAX_REPORTED_ISSUES = 200
MAX_PAYLOAD_CHARS = 1500


@dataclass
class BuildConfig:
    seed: int = DEFAULT_SEED
    val_fraction: float = 0.15
    augment: bool = True
    embed_rate: float = 1.0  # expected embeddings per positive train example
    obfuscation_rate: float = 0.5  # share of positives that get one obfuscated variant
    benign_obfuscation_rate: float = 0.1  # benign variants keep obfuscation from becoming a label shortcut
    benign_concat_rate: float = 1.0  # benign concatenations per embedding


@dataclass
class _Item:
    record: DatasetRecord
    batch: str
    kind: str  # raw | external
    hash: str


@dataclass
class BuildReport:
    data_dir: str
    splits: dict[str, dict[str, Any]] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)


def _split_for_test_batch(batch: str, kind: str, lang: str) -> str:
    if kind == "external":
        name = re.sub(r"[^a-z0-9]+", "_", batch[len("test-"):].lower()).strip("_") or "external"
        return f"test_ext_{name}"
    return f"test_{lang}"


def is_test_batch(batch: str) -> bool:
    return batch.startswith("test-")


def _load(data_dir: Path) -> tuple[list[_Item], dict[str, Any]]:
    files: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    warning_counts: Counter[str] = Counter()
    invalid_count = 0
    items: list[_Item] = []
    seen_ids: dict[str, str] = {}
    for kind in ("raw", "external"):
        folder = data_dir / kind
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.jsonl")):
            batch = path.stem
            n_lines = n_valid = 0
            for lineno, line in iter_jsonl(path):
                n_lines += 1
                where = f"{kind}/{path.name}:{lineno}"
                try:
                    data = json.loads(line)
                    if not isinstance(data, dict):
                        raise ValueError("line is not a JSON object")
                    rec = DatasetRecord.model_validate(data)
                except (json.JSONDecodeError, ValueError, ValidationError) as exc:
                    invalid_count += 1
                    if len(invalid) < MAX_REPORTED_ISSUES:
                        invalid.append({"where": where, "error": _short_error(exc)})
                    continue
                if rec.id in seen_ids:
                    invalid_count += 1
                    if len(invalid) < MAX_REPORTED_ISSUES:
                        invalid.append({"where": where, "error": f"duplicate id {rec.id!r} (first in {seen_ids[rec.id]})"})
                    continue
                seen_ids[rec.id] = where
                if not rec.source:
                    rec.source = f"{kind}/{batch}"
                for w in rec.warnings():
                    warning_counts[w] += 1
                    if len(warnings) < MAX_REPORTED_ISSUES:
                        warnings.append({"where": where, "id": rec.id, "warning": w})
                n_valid += 1
                items.append(_Item(rec, batch, kind, text_hash(rec.text)))
            files.append({"path": f"{kind}/{path.name}", "batch": batch, "kind": kind,
                          "test_batch": is_test_batch(batch), "lines": n_lines, "valid": n_valid,
                          "invalid": n_lines - n_valid})
    report = {
        "files": files,
        "invalid": {"count": invalid_count, "examples": invalid},
        "warnings": {"count": sum(warning_counts.values()), "by_type": dict(warning_counts), "examples": warnings},
    }
    return items, report


def _short_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        parts = []
        for err in exc.errors()[:5]:
            loc = ".".join(str(p) for p in err.get("loc", ())) or "record"
            parts.append(f"{loc}: {err.get('msg')}")
        return "; ".join(parts)
    return str(exc)[:300]


def _dedupe(items: list[_Item]) -> tuple[list[_Item], dict[str, Any]]:
    """Drop duplicate normalised texts; test copies win; texts with conflicting labels are dropped."""
    labels_by_hash: dict[str, set[int]] = defaultdict(set)
    for it in items:
        labels_by_hash[it.hash].add(it.record.label)
    conflicts = {h for h, labels in labels_by_hash.items() if len(labels) > 1}
    ordered = sorted(items, key=lambda it: (not is_test_batch(it.batch), it.kind != "raw"))
    kept: list[_Item] = []
    seen: dict[str, _Item] = {}
    removed = cross = 0
    conflict_ids: list[str] = []
    for it in ordered:
        if it.hash in conflicts:
            conflict_ids.append(it.record.id)
            continue
        first = seen.get(it.hash)
        if first is not None:
            removed += 1
            if is_test_batch(first.batch) != is_test_batch(it.batch):
                cross += 1
            continue
        seen[it.hash] = it
        kept.append(it)
    return kept, {"removed": removed, "cross_split_removed": cross, "label_conflicts": len(conflicts),
                  "label_conflict_ids": conflict_ids[:MAX_REPORTED_ISSUES]}


def _stratified_split(items: list[_Item], val_fraction: float, rng: random.Random) -> tuple[list[_Item], list[_Item]]:
    strata: dict[tuple[int, str], list[_Item]] = defaultdict(list)
    for it in items:
        strata[(it.record.label, it.record.lang)].append(it)
    train: list[_Item] = []
    val: list[_Item] = []
    for key in sorted(strata):
        group = sorted(strata[key], key=lambda it: it.record.id)
        rng.shuffle(group)
        n_val = int(round(len(group) * val_fraction))
        if n_val == 0 and len(group) >= 3 and val_fraction > 0:
            n_val = 1
        val.extend(group[:n_val])
        train.extend(group[n_val:])
    return train, val


def _record_dict(rec: DatasetRecord, batch: str | None = None) -> dict[str, Any]:
    data = rec.model_dump()
    if batch is not None:
        data.setdefault("batch", batch)
    return data


def _augment(train: list[dict[str, Any]], cfg: BuildConfig, rng: random.Random) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    positives = [r for r in train if r["label"] == 1 and len(r["text"]) <= MAX_PAYLOAD_CHARS]
    carriers = [r for r in train if r["label"] == 0 and len(r["text"]) >= 40]
    carriers_by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in carriers:
        carriers_by_lang[c["lang"]].append(c)
    out: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    positions = ("start", "middle", "end")

    def pick_carrier(lang: str) -> dict[str, Any] | None:
        pool = carriers_by_lang.get(lang) or carriers
        return rng.choice(pool) if pool else None

    for p in positives:
        n_embed = int(cfg.embed_rate) + (1 if rng.random() < cfg.embed_rate - int(cfg.embed_rate) else 0)
        for k in range(n_embed):
            carrier = pick_carrier(p["lang"])
            if carrier is None:
                break
            pos = positions[rng.randrange(3)]
            lang = p["lang"] if carrier["lang"] == p["lang"] else "mixed"
            out.append({**p, "id": f"{p['id']}~aug-embed-{pos}-{k}", "text": embed_in_carrier(p["text"], carrier["text"], pos, rng),
                        "lang": lang, "carrier": carrier["carrier"], "source": f"aug/embed-{pos}",
                        "notes": f"payload={p['id']} carrier={carrier['id']}"})
            counts[f"embed_{pos}"] += 1
    n_embeds = sum(v for k, v in counts.items() if k.startswith("embed_"))
    n_concat = int(round(n_embeds * cfg.benign_concat_rate))
    for k in range(n_concat if len(carriers) >= 2 else 0):
        a, b = rng.sample(carriers, 2)
        lang = a["lang"] if a["lang"] == b["lang"] else "mixed"
        out.append({**a, "id": f"{a['id']}~aug-concat-{k}", "text": f"{a['text'].strip()}\n\n{b['text'].strip()}",
                    "lang": lang, "variety": a["variety"] if lang != "mixed" else "mixed",
                    "source": "aug/concat-benign", "notes": f"carriers={a['id']},{b['id']}"})
        counts["concat_benign"] += 1
    for r in train:
        rate = cfg.obfuscation_rate if r["label"] == 1 else cfg.benign_obfuscation_rate
        if rng.random() >= rate:
            continue
        kinds = OBFUSCATIONS_BY_LANG.get(r["lang"], OBFUSCATIONS_BY_LANG["en"])
        kind = kinds[rng.randrange(len(kinds))]
        variant = obfuscate(r["text"], kind, rng)
        if variant == r["text"]:
            continue
        out.append({**r, "id": f"{r['id']}~aug-{kind}", "text": variant, "source": f"aug/obf-{kind}",
                    "notes": f"variant_of={r['id']}"})
        counts[f"obf_{kind}"] += 1
    return out, dict(counts)


def _split_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_label = Counter(str(r["label"]) for r in records)
    by_lang = Counter(r["lang"] for r in records)
    by_label_lang = Counter(f"{r['label']}/{r['lang']}" for r in records)
    by_variety = Counter(r["variety"] for r in records)
    by_attack = Counter(r["attack_type"] for r in records)
    augmented = sum(1 for r in records if str(r.get("source", "")).startswith("aug/"))
    return {"total": len(records), "by_label": dict(by_label), "by_lang": dict(by_lang),
            "by_label_lang": dict(by_label_lang), "by_variety": dict(by_variety),
            "by_attack_type": dict(by_attack), "augmented": augmented}


def build_dataset(data_dir: str | Path, *, config: BuildConfig | None = None,
                  out_dir: str | Path | None = None) -> BuildReport:
    """Validate, dedupe, split and augment; write ``splits/*.jsonl`` and ``splits/stats.json``."""
    cfg = config or BuildConfig()
    data_dir = Path(data_dir)
    out = Path(out_dir) if out_dir is not None else data_dir / "splits"
    rng = random.Random(cfg.seed)  # noqa: S311  # nosec B311 - reproducible data split, not security

    items, load_report = _load(data_dir)
    items, dup_report = _dedupe(items)

    splits: dict[str, list[dict[str, Any]]] = {name: [] for name in CORE_SPLITS}
    batches: dict[str, set[str]] = defaultdict(set)
    pool: list[_Item] = []
    for it in items:
        if is_test_batch(it.batch):
            name = _split_for_test_batch(it.batch, it.kind, it.record.lang)
            splits.setdefault(name, []).append(_record_dict(it.record, it.batch))
            batches[it.batch].add(name)
        else:
            pool.append(it)
            batches[it.batch].add("train/val")
    train_items, val_items = _stratified_split(pool, cfg.val_fraction, rng)
    splits["train"] = [_record_dict(it.record, it.batch) for it in train_items]
    splits["val"] = [_record_dict(it.record, it.batch) for it in val_items]

    aug_counts: dict[str, Any] = {}
    if cfg.augment and splits["train"]:
        augmented, aug_counts = _augment(splits["train"], cfg, rng)
        splits["train"].extend(augmented)

    # leakage check: no test text (normalised hash) or id may appear in train/val
    test_hashes = {text_hash(r["text"]) for name, recs in splits.items() if name.startswith("test_") for r in recs}
    test_ids = {r["id"] for name, recs in splits.items() if name.startswith("test_") for r in recs}
    leaked_hashes = sum(1 for name in ("train", "val") for r in splits[name] if text_hash(r["text"]) in test_hashes)
    leaked_ids = sum(1 for name in ("train", "val") for r in splits[name] if r["id"].split("~")[0] in test_ids)
    if leaked_hashes or leaked_ids:
        log.warning("leakage check failed: %d texts / %d ids from test splits in train/val", leaked_hashes, leaked_ids)
        # augmented variants that collide with a test text are removed rather than shipped
        splits["train"] = [r for r in splits["train"] if text_hash(r["text"]) not in test_hashes]

    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("test_ext_*.jsonl"):
        if stale.stem not in splits:
            stale.unlink()
    for name, recs in splits.items():
        write_jsonl(out / f"{name}.jsonl", recs)

    stats = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data_dir": str(data_dir),
        "seed": cfg.seed,
        "val_fraction": cfg.val_fraction,
        "augment": cfg.augment,
        "inputs": load_report["files"],
        "invalid": load_report["invalid"],
        "warnings": load_report["warnings"],
        "duplicates": dup_report,
        "batches": {b: sorted(s) for b, s in sorted(batches.items())},
        "augmentation": aug_counts,
        "leakage_check": {"ok": not (leaked_hashes or leaked_ids), "test_texts_in_train_val": leaked_hashes,
                          "test_ids_in_train_val": leaked_ids},
        "splits": {name: _split_stats(recs) for name, recs in splits.items()},
    }
    (out / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("dataset built: %s", {k: v["total"] for k, v in stats["splits"].items()})
    return BuildReport(str(data_dir), {k: v for k, v in stats["splits"].items()}, stats)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mirsad.detector.build_dataset", description=__doc__.split("\n")[0])
    parser.add_argument("--data", default="data/detector", help="dataset root containing raw/ and external/")
    parser.add_argument("--out", default=None, help="output directory (default: <data>/splits)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--no-augment", action="store_true")
    parser.add_argument("--embed-rate", type=float, default=1.0)
    parser.add_argument("--obfuscation-rate", type=float, default=0.5)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if not 0.0 <= args.val_fraction < 1.0:
        parser.error("--val-fraction must be in [0, 1)")
    cfg = BuildConfig(seed=args.seed, val_fraction=args.val_fraction, augment=not args.no_augment,
                      embed_rate=args.embed_rate, obfuscation_rate=args.obfuscation_rate)
    report = build_dataset(args.data, config=cfg, out_dir=args.out)
    st = report.stats
    print(f"invalid lines skipped: {st['invalid']['count']}  warnings: {st['warnings']['count']}  "
          f"duplicates removed: {st['duplicates']['removed']}  label conflicts: {st['duplicates']['label_conflicts']}")
    for name, s in st["splits"].items():
        print(f"  {name:<22} {s['total']:>6}  labels={s['by_label']}  langs={s['by_lang']}  aug={s['augmented']}")
    print(f"leakage check: {'OK' if st['leakage_check']['ok'] else 'FAILED'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
