import hashlib
import os
import json

# Check raw extract integrity
source_dir = r'C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Resources\Capstone Questions\Capstone 2\data'
for fname in ['customers.csv', 'products.csv', 'orders.csv']:
    path = os.path.join(source_dir, fname)
    with open(path, 'rb') as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    print(f'{fname}: {sha}')

# Compare with manifest
with open(r'C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Projects\Individual\Manas Dutt\Week 3\QuickMart\data\raw_manifest.json', 'r') as f:
    manifest = json.load(f)

for table in ['customers', 'products', 'orders']:
    expected = manifest[table]['sha256']
    path = os.path.join(source_dir, f'{table}.csv')
    with open(path, 'rb') as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    match = expected == actual
    print(f'{table}.csv: manifest={expected[:16]}... actual={actual[:16]}... match={match}')