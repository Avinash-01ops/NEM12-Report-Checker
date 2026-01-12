# NEM12 Validator

Project to validate NEM12 energy reports against meter readings stored in PostgreSQL.

Goals:
- Compare interval values (30-minute) between NEM12 and meter readings
- Validate quality flag mappings
- Report missing intervals and discrepancies
- Generate a comprehensive validation report and metrics

Quickstart

1. Create a virtualenv and install requirements:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Configure DB credentials (use env vars or `configs/config.ini`)
3. Run validation:

```bash
python scripts/run_validation.py --config configs/config.ini
```
