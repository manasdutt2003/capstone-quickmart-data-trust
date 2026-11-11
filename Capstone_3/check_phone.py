import pandas as pd

df = pd.read_csv(r'C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Projects\Individual\Manas Dutt\Week 3\QuickMart\outputs\trusted_orders.csv')

target = '0741763684'
for col in df.columns:
    if df[col].astype(str).str.contains(target, na=False).any():
        print(f'Found in column: {col}')
        matches = df[df[col].astype(str).str.contains(target, na=False)]
        print(f'  Count: {len(matches)}')
        print(f'  Sample: {matches[col].head(3).tolist()}')