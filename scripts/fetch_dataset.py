"""Download the workbook from the linked UCI Online Retail dataset repository."""
from pathlib import Path
from urllib.request import urlretrieve

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/"data"/"online_retail.xlsx"
COMMIT="08cab3abecf21bcb00c4698de10324dfe50ec9c8"
URL=f"https://raw.githubusercontent.com/ratharin1223-lab/UCI-online-Retail-Dataset/{COMMIT}/Online%20Retail.xlsx"

def main() -> None:
    DEST.parent.mkdir(parents=True,exist_ok=True)
    urlretrieve(URL,DEST)
    print(f"Downloaded {DEST} ({DEST.stat().st_size:,} bytes)")

if __name__=="__main__": main()
