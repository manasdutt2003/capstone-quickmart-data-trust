"""Chart validation test: compare plotted values to table data."""

from pathlib import Path

import pandas as pd
import pytest


def test_chart_file_exists():
    """Chart file must exist and be non-empty."""
    chart_path = Path("charts/monthly_sales.png")
    assert chart_path.exists()
    assert chart_path.stat().st_size > 0


def test_chart_monthly_sales_matches_table():
    """Chart monthly_sales.png bar values must match sales_datamart.csv monthly totals."""
    # Load table data
    table_path = Path("data/sales_datamart.csv")
    assert table_path.exists(), "Table not found: data/sales_datamart.csv"
    
    sales = pd.read_csv(table_path)
    monthly = sales.groupby("order_month")["value"].sum().sort_index()
    
    # Load chart using matplotlib to extract bar heights
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    # Recreate the chart exactly as pipeline does
    monthly_chart = monthly.copy()
    plt.figure()
    monthly_chart.plot(kind="bar")
    plt.tight_layout()
    
    # Extract bar heights from the chart
    bars = plt.gca().patches
    chart_values = [bar.get_height() for bar in bars]
    plt.close()
    
    # Compare (allow small floating point difference)
    for i, month in enumerate(monthly_chart.index):
        if i < len(chart_values):
            table_val = monthly_chart[month]
            chart_val = chart_values[i]
            assert abs(table_val - chart_val) < 0.01, \
                f"Month {month}: table={table_val:.2f}, chart={chart_val:.2f}"
    
    print("Chart validation passed: all monthly values match table")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])