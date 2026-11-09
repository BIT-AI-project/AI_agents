from pathlib import Path
from autoanalyst.dataset.validator import validate_dataset
from autoanalyst.evaluation.golden import validate_golden_references

def test_committed_golden_reference_values(config):
    validate_dataset(config.dataset_path)
    golden=Path(__file__).resolve().parents[2]/"eval"/"golden"/"checks.json"
    result=validate_golden_references(config.dataset_path,golden)
    assert result["checks"]==50 and result["valid"]
