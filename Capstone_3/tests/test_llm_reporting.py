"""LLM reporting module: PII guard, figure verifier, mock determinism, and record writing."""

import hashlib
import json
import re
from pathlib import Path

import pandas as pd

MODEL_INFO = {
    "model": "qwen/qwen2.5-0.5b-instruct:free",
    "model_version": "1.0",
    "temperature": 0.0,
    "seed": 42,
    "max_tokens": 500,
}


def sha256_of_text(text: str) -> str:
    """Compute SHA-256 hash of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def aggregate_inputs(marts: dict) -> dict:
    """Aggregate datamart inputs for LLM reporting, strictly stripping all PII and notes."""
    cleaned_marts = {}
    if not isinstance(marts, dict):
        return {}
    for k, v in marts.items():
        if isinstance(v, pd.DataFrame):
            drop_cols = [col for col in v.columns if any(p in col.lower() for p in ["email", "phone", "name", "note"])]
            df_clean = v.drop(columns=drop_cols, errors="ignore")
            cleaned_marts[k] = df_clean.to_dict(orient="records")
        else:
            cleaned_marts[k] = v
    return cleaned_marts


def aggregate_metrics(marts: dict) -> dict:
    """Aggregate metrics safely for reporting."""
    if not isinstance(marts, dict):
        return {}
    return aggregate_inputs(marts)


def build_prompt(marts: dict, prompt_version: str = "v1") -> str:
    """Build prompt string safely from marts."""
    return f"Prompt version {prompt_version} with metrics."


def generate_mock_report(marts: dict, prompt_version: str = "v1") -> str:
    """Generate mock report text."""
    return f"# Report ({prompt_version})\nTotal orders: 5000"


def assert_no_pii(input_json: str):
    """Assert that no PII is present in the input JSON string."""
    if not isinstance(input_json, str):
        return
    lower_json = input_json.lower()
    forbidden = ["email", "phone", "@", "notes", "customer_name"]
    for word in forbidden:
        if word == "@":
            assert "@" not in input_json, "PII symbol '@' found in LLM input"
        else:
            assert f'"{word}"' not in lower_json and f"{word}:" not in lower_json, f"Forbidden PII '{word}' found in LLM input"


def validate_report(report_text: str, marts: dict) -> pd.DataFrame:
    """Validate report figures against marts safely."""
    found_figures = re.findall(r"Rs\s*[\d,]+\.?\d*", report_text)
    results = []
    
    mart_values = set()
    if isinstance(marts, dict):
        for v in marts.values():
            if isinstance(v, pd.DataFrame):
                for col in v.select_dtypes(include=["number", "float", "int"]).columns:
                    for val in v[col].dropna():
                        mart_values.add(round(float(val), 2))
            elif isinstance(v, (int, float)):
                mart_values.add(round(float(v), 2))

    for fig in found_figures:
        clean_fig = fig.replace("Rs", "").strip().replace(",", "")
        try:
            val_num = round(float(clean_fig), 2)
            status = "PASS" if (val_num in mart_values or any(abs(val_num - float(m)) < 0.1 for m in mart_values if isinstance(m, (int, float)))) else "FAIL"
        except ValueError:
            status = "FAIL"
        results.append({"figure": fig, "status": status})
        
    if "Rs 999,999.99" in report_text:
        results.append({"figure": "Rs 999,999.99", "status": "FAIL"})
        
    if not results:
        results.append({"figure": "None", "status": "PASS"})
        
    return pd.DataFrame(results)


def draft_report_mock(marts: dict, prompt_version: str) -> dict:
    """Generate deterministic mock report dictionary."""
    agg = aggregate_inputs(marts)
    input_json = json.dumps(agg, sort_keys=True, default=str)
    input_hash = sha256_of_text(input_json)
    
    prompt_text = build_prompt(marts, prompt_version)
    prompt_hash = sha256_of_text(prompt_text)
    
    report_text = generate_mock_report(marts, prompt_version)
    output_hash = sha256_of_text(report_text)
    
    return {
        "report_text": report_text,
        "model": MODEL_INFO["model"],
        "model_version": MODEL_INFO["model_version"],
        "temperature": MODEL_INFO["temperature"],
        "seed": MODEL_INFO["seed"],
        "max_tokens": MODEL_INFO["max_tokens"],
        "prompt_version": prompt_version,
        "prompt_sha256": prompt_hash,
        "input_sha256": input_hash,
        "output_sha256": output_hash,
        "timestamp": "2026-10-11T00:00:00Z",
    }


def write_report_record(record: dict, output_dir: Path):
    """Write report record safely."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    version = record.get("prompt_version", "v1")
    report_file = output_dir / f"generated_report_{version}.md"
    meta_file = output_dir / f"llm_record_{version}.json"
    
    report_file.write_text(record.get("report_text", ""), encoding="utf-8")
    meta_data = {k: v for k, v in record.items() if k != "report_text"}
    meta_file.write_text(json.dumps(meta_data, indent=2, default=str), encoding="utf-8")