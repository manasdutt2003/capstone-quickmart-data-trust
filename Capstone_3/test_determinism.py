import hashlib
import os
import sys
import subprocess
from pathlib import Path

def run_pipeline(output_dir):
    """Run pipeline and return hashes of outputs."""
    # Run as module
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

# Run 1
print("Running pipeline (run 1)...")
hashes1 = run_pipeline(Path(r'C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Projects\Individual\Manas Dutt\Week 3\QuickMart'))
if hashes1:
    print('Run 1 hashes:')
    for k, v in hashes1.items():
        print(f'  {k}: {v}')

# Run 2
print("\nRunning pipeline (run 2)...")
hashes2 = run_pipeline(Path(r'C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Projects\Individual\Manas Dutt\Week 3\QuickMart'))
if hashes2:
    print('Run 2 hashes:')
    for k, v in hashes2.items():
        print(f'  {k}: {v}')

if hashes1 and hashes2:
    print(f'\nMatch: {hashes1 == hashes2}')
    if hashes1 != hashes2:
        for k in hashes1:
            if k in hashes2 and hashes1[k] != hashes2[k]:
                print(f'  MISMATCH: {k}')
                print(f'    Run 1: {hashes1[k]}')
                print(f'    Run 2: {hashes2[k]}')