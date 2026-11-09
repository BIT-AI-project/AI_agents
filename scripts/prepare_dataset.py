from autoanalyst.config import AppConfig
from autoanalyst.dataset.loader import build_database

if __name__ == "__main__":
    config=AppConfig.load()
    workbook=config.dataset_path.with_name("online_retail.xlsx")
    print(build_database(workbook,config.dataset_path))
