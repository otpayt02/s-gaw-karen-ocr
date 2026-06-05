import os
chunk_size = 90 * 1024 * 1024
input_file = r'C:\Users\olive\Projects\karen_lang_trans\karen_dataset_yolov8.zip'
with open(input_file, 'rb') as f:
    i = 0
    while chunk := f.read(chunk_size):
        out = f'C:\\Users\\olive\\Projects\\karen_lang_trans\\dataset_part_{i:03d}.bin'
        with open(out, 'wb') as o:
            o.write(chunk)
        print(f'Written part {i:03d} — {len(chunk)/1024/1024:.1f} MB')
        i += 1
print(f'Done. {i} parts total.')