# Assumptions

1. **Commission rate = 8% (0.08).** The project brief (`QuickMart_Mock_Project.html`) states no commission rate — searched for "commission" (scenario text only, no rate), "8%", "0.08", and "eight percent": none present. Single config constant: `config/settings.json` → `commission_rate`. `src/commission.py: COMMISSION_RATE` mirrors it as the code default; `src/pipeline.py` passes the settings rate explicitly into `build_commission_datamart(rate=rate)` and `commission_frame(..., rate)`. If finance states a different rate, change only `config/settings.json` and rerun the pipeline.
