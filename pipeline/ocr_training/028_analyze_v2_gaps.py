import json, os

VAL_RESULTS    = "/root/karenlangtrans/027_v2_val_results.json"
INDEX_MAP      = "/root/karenlangtrans/karen_index_map.json"
OUTPUT_JSON    = "/root/karenlangtrans/028_v2_gap_report.json"
MISS_THRESHOLD = 0.50

if not os.path.exists(VAL_RESULTS):
    print(f"[028] ERROR: {VAL_RESULTS} not found. Run 027 first."); exit(1)

index_map = {}
if os.path.exists(INDEX_MAP):
    with open(INDEX_MAP) as f:
        index_map = json.load(f)
    print(f"[028] Index map loaded: {len(index_map)} entries")

with open(VAL_RESULTS) as f:
    data = json.load(f)

per_class = data["per_class"]
summary   = data["summary"]
missed, weak = [], []

for e in per_class:
    name = index_map.get(str(e["class_idx"]), str(e["class_idx"]))
    rec  = {"class_idx": e["class_idx"], "syllable": name, "mAP50": e["mAP50"], "recall": e["recall"], "precision": e["precision"]}
    if e["mAP50"] < MISS_THRESHOLD: missed.append(rec)
    elif e["mAP50"] < 0.80: weak.append(rec)

missed.sort(key=lambda x: x["mAP50"])
weak.sort(key=lambda x: x["mAP50"])

report = {"model": data["model"], "overall_mAP50": summary["overall_mAP50"], "total_classes": summary["num_classes"], "missed_count": len(missed), "weak_count": len(weak), "missed_classes": missed, "weak_classes": weak}

with open(OUTPUT_JSON, "w") as f:
    json.dump(report, f, indent=2)

print(f"\n[028] GAP ANALYSIS COMPLETE")
print(f"[028] Total classes:    {summary['num_classes']}")
print(f"[028] Still missed:     {len(missed)}   (mAP50 < {MISS_THRESHOLD})")
print(f"[028] Weak (0.50-0.80): {len(weak)}")
print(f"[028] v1 missed was:    149")
print(f"[028] v2 missed is:     {len(missed)}")
if len(missed) < 50: print("[028] TARGET HIT — v2 ready for Phase 2.")
else: print(f"[028] {len(missed)} still below threshold — plan v3.")
if missed:
    print("\n[028] Top 10 hardest remaining:")
    for e in missed[:10]: print(f"       idx={e['class_idx']:5d}  {e['syllable']:20s}  mAP50={e['mAP50']:.4f}")
print(f"\n[028] Full report: {OUTPUT_JSON}")