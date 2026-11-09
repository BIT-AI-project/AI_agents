from pathlib import Path
import pytest
from autoanalyst.config import AppConfig

@pytest.fixture
def config(tmp_path):
    root=Path(__file__).resolve().parents[1]
    return AppConfig(dataset_path=root/"data"/"online_retail.sqlite",output_dir=tmp_path)
