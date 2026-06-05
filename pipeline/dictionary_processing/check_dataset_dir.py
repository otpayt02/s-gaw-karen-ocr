import yaml
with open('/root/karen_dataset_yolov8/data.yaml', 'r') as f:
    cfg = yaml.safe_load(f)
names = cfg['names']
print('Total classes:', len(names))
print('First 10:', names[:10])
print('Last 10:', names[-10:])
non_numeric = [n for n in names if not str(n).isdigit()]
print('Non-numeric (2025 paradigm):', len(non_numeric))
print('Examples:', non_numeric[:10])