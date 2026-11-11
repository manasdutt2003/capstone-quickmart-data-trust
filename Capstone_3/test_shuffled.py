import hashlib
import os
import sys
import subprocess
import pandas as pd
from pathlib import Path

def load_raw_data():
    """Load raw data from source."""
    from src.data_loader import load_all_text
    raw = load_all_text(Path(r'C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Resources\Capstone Questions\Capstone 2\data'))
    return {
        'customers': pd.DataFrame(raw['customers']),
        'products': pd.DataFrame(raw['products']),
        'orders': pd.DataFrame(raw['orders']),
    }

def run_pipeline_with_data(customers, products, orders, output_dir):
    """Run pipeline with specific data."""
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path(r'C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Projects\Individual\Manas Dutt\Week 3\QuickMart\src'))
    
    result = subprocess.run(
        [sys.executable, '-m', 'src.pipeline'],
        cwd=r'C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Projects\Individual\Manas Dutt\Week 3\QuickMart',
        capture_output=True,
        text=True,
        env=env
    )
    
    if result.returncode != 0:
        print(f"Pipeline failed: {result.stderr}")
        return None
    
    hashes = {}
    output_path = Path(r'C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Projects\Individual\Manas Dutt\Week 3\QuickMart\outputs')
    for f in sorted(os.listdir(output_path)):
        if f.endswith('.csv') or f.endswith('.md'):
            with open(os.path.join(output_path, f), 'rb') as fp:
                hashes[f] = hashlib.sha256(fp.read()).hexdigest()
    return hashes

# Load raw data
print("Loading raw data...")
raw_data = load_raw_data()
customers = raw_data['customers']
products = raw_data['products']
orders = raw_data['orders']

# Shuffle rows with fixed seed
print("Shuffling data...")
customers_shuffled = customers.sample(frac=1, random_state=42).reset_index(drop=True)
products_shuffled = products.sample(frac=1, random_state=42).reset_index(drop=True)
orders_shuffled = orders.sample(frac=1, random_state=42).reset_index(drop=True)

raw_dir = Path(r'C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Resources\Capstone Questions\Capstone 2\data')

original_customers = raw_dir / 'customers.csv'
original_products = raw_dir / 'products.csv'
original_orders = raw_dir / 'orders.csv'

# Backup original safely (delete old backups if they exist)
print("Backing up original data...")
for orig in [original_customers, original_products, original_orders]:
    bak = orig.with_suffix('.csv.bak')
    if bak.exists():
        bak.unlink()  # Removes old backup file so rename doesn't crash
    if orig.exists():
        orig.rename(bak)

try:
    # Write shuffled data
    customers_shuffled.to_csv(original_customers, index=False, encoding='utf-8', lineterminator='\n')
    products_shuffled.to_csv(original_products, index=False, encoding='utf-8', lineterminator='\n')
    orders_shuffled.to_csv(original_orders, index=False, encoding='utf-8', lineterminator='\n')
    
    # Run pipeline
    print("Running pipeline with shuffled data...")
    hashes = run_pipeline_with_data(customers_shuffled, products_shuffled, orders_shuffled, Path('.'))
    print('Shuffled run hashes:')
    if hashes:
        for k, v in hashes.items():
            print(f'  {k}: {v}')
finally:
    # Restore original safely
    print("Restoring original data...")
    for orig in [original_customers, original_products, original_orders]:
        bak = orig.with_suffix('.csv.bak')
        if orig.exists():
            orig.unlink()  # Remove temporary shuffled file
        if bak.exists():
            bak.rename(orig) # Restore original backup

# Now run with original data to compare
print("\nRunning pipeline with original data...")
hashes_orig = run_pipeline_with_data(customers, products, orders, Path('.'))
print('Original run hashes:')
if hashes_orig:
    for k, v in hashes_orig.items():
        print(f'  {k}: {v}')

if hashes and hashes_orig:
    print(f'\nMatch: {hashes == hashes_orig}')
    if hashes != hashes_orig:
        for k in hashes:
            if k in hashes_orig and hashes[k] != hashes_orig[k]:
                print(f'  MISMATCH: {k}')
                print(f'    Shuffled: {hashes[k]}')
                print(f'    Original: {hashes_orig[k]}')