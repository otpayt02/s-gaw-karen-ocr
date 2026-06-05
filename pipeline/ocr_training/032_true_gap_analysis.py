import json, os

VAL_RESULTS  = "/root/karenlangtrans/027_v2_val_results.json"
INDEX_MAP    = "/root/karen_lang_trans/karen_index_map.json"
VALID_LBL    = "/root/karen_dataset_yolov8/valid/labels"
OUTPUT_JSON  = "/root/karenlangtrans/032_true_gap_report.json"
MISS_THRESH  = 0.50

# Count how many validation instances exist per class from label files
print("[032] Counting validation instances per class from label files...")
val_instance_counts = {}
for fname in os.listdir(VALID_LBL):
    if not fname.endswith(".txt"): continue
    with open(os.path.join(VALID_LBL, fname)) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            class_idx = int(line.split()[0])
            val_instance_counts[class_idx] = val_instance_counts.get(class_idx, 0) + 1

classes_with_val = len(val_instance_counts)
print(f"[032] Classes with val coverage: {classes_with_val}")
print(f"[032] Total val instances:       {sum(val_instance_counts.values())}")

with open(VAL_RESULTS) as f: data = json.load(f)
index_map = {}
if os.path.exists(INDEX_MAP):
    with open(INDEX_MAP) as f: index_map = json.load(f)

per_class = data["per_class"]
summary   = data["summary"]

missed, weak, no_val = [], [], []

for e in per_class:
    idx  = e["class_idx"]
    name = index_map.get(str(idx), str(idx))
    inst = val_instance_counts.get(idx, 0)
    rec  = {"class_idx": idx, "syllable": name, "mAP50": e["mAP50"],
            "recall": e["recall"], "precision": e["precision"], "val_instances": inst}
    if inst == 0:
        no_val.append(rec)
    elif e["mAP50"] < MISS_THRESH:
        missed.append(rec)
    elif e["mAP50"] < 0.80:
        weak.append(rec)

missed.sort(key=lambda x: x["mAP50"])
weak.sort(key=lambda x: x["mAP50"])

report = {
    "model":               data["model"],
    "overall_mAP50":       summary["overall_mAP50"],
    "overall_recall":      summary["overall_recall"],
    "total_classes":       summary["num_classes"],
    "classes_with_val":    classes_with_val,
    "classes_no_val":      len(no_val),
    "truly_missed":        len(missed),
    "weak_count":          len(weak),
    "missed_classes":      missed,
    "weak_classes":        weak,
    "no_val_classes":      no_val,
}

with open(OUTPUT_JSON, "w") as f:
    json.dump(report, f, indent=2)

print(f"\n[032] TRUE GAP ANALYSIS COMPLETE")
print(f"[032] Total trained classes:     {summary['num_classes']}")
print(f"[032] Classes WITH val images:   {classes_with_val}")
print(f"[032] Classes with NO val images:{len(no_val)}  (untestable — not failed)")
print(f"[032] TRULY missed (has val, mAP50 < 0.50): {len(missed)}")
print(f"[032] Weak (0.50-0.80):          {len(weak)}")
print(f"[032] v1 missed was:             149")
print(f"[032] v3 truly missed is:        {len(missed)}")

if len(missed) < 50:
    print("[032] TARGET HIT — v3 ready for Phase 2 real document inference.")
else:
    print(f"[032] {len(missed)} truly missed — plan v4 targeting these classes.")

if missed:
    print(f"\n[032] Top 10 truly hardest (has val images, still failing):")
    for e in missed[:10]:
        print(f"       idx={e['class_idx']:5d}  {e['syllable']:20s}  mAP50={e['mAP50']:.4f}  val_inst={e['val_instances']}")

print(f"\n[032] Full report: {OUTPUT_JSON}")