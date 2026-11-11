"""Report Validation Engine: every figure must reconcile to datamarts."""

import re
from pathlib import Path

import pandas as pd


def extract_numbers(text):
    """Extract all numeric claims from report text."""
    patterns = [
        (r"Rs([\d,]+\.?\d*)", "currency"),
        (r"([\d,]+\.?\d*)%", "percentage"),
        (r"(\d+(?:,\d{3})*(?:\.\d+)?)", "number"),
    ]
    numbers = []
    for pattern, num_type in patterns:
        for match in re.finditer(pattern, text):
            value_str = match.group(1).replace(",", "")
            try:
                value = float(value_str)
                context = text[max(0, match.start() - 50):match.end() + 50]
                numbers.append({
                    "value": value,
                    "type": num_type,
                    "context": context.strip(),
                    "position": match.start(),
                })
            except ValueError:
                continue
    return numbers


def validate_number(value, num_type, context, datamarts, tolerance=0.01):
    """Validate a single number against datamarts."""
    search_values = []
    for df in datamarts.values():
        for col in df.select_dtypes(include=["number"]).columns:
            search_values.extend(df[col].dropna().tolist())
    search_values = list({round(v, 2) for v in search_values})
    best_match = min(search_values, key=lambda x: abs(x - value)) \
        if search_values else None
    matched = best_match is not None and abs(best_match - value) <= tolerance
    return {
        "claimed_value": value,
        "type": num_type,
        "matched": matched,
        "datamart_value": best_match if matched else None,
        "difference": abs(best_match - value) if matched else None,
        "context": context[:100],
    }


def validate_report(report_text, datamarts):
    """Validate all numbers in report against datamarts."""
    numbers = extract_numbers(report_text)
    results = []
    for num in numbers:
        validation = validate_number(num["value"], num["type"],
                                     num["context"], datamarts)
        validation["original_context"] = num["context"]
        results.append(validation)
    return pd.DataFrame(results)


def reconcile_report(report_path, datamarts):
    """Validate report from file."""
    with open(report_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    return validate_report(text, datamarts)


def generate_validation_report(validation_df, out_path):
    """Generate validation report in Markdown."""
    total = len(validation_df)
    passed = int(validation_df["matched"].sum())
    failed = total - passed
    lines = [
        "# Report Validation Results",
        "",
        f"**Total Figures Checked**: {total}",
        f"**Passed**: {passed}",
        f"**Failed**: {failed}",
        f"**Pass Rate**: {passed / total * 100:.1f}%"
        if total > 0 else "N/A",
        "",
        "## Details",
        "",
        "| Claimed | Matched | Datamart Value | Diff | Type | Context |",
        "|---------|---------|----------------|------|------|---------|",
    ]
    for _, row in validation_df.iterrows():
        status = "PASS" if row["matched"] else "FAIL"
        lines.append(
            "| {} | {} | {} | {} | {} | {}... |".format(
                row["claimed_value"], status,
                row["datamart_value"] if row["datamart_value"] else "N/A",
                row["difference"] if row["difference"] else "N/A",
                row["type"], row["original_context"][:50]))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def verify_all_claims(datamarts, generated_report):
    """Main validation entry point."""
    validation_df = validate_report(generated_report, datamarts)
    all_passed = bool(validation_df["matched"].all()) \
        if len(validation_df) > 0 else True
    return validation_df, all_passed
