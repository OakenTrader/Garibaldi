from extractor import Extractor
from pathlib import Path
import json

def extract_common():
    """
    Extracts common data (presumably from text files) found in the "common" directory
    and saves it as JSON files in a corresponding "common_json" directory.

    Problem with 00_mobilization_option.txt at line 602 (not wholly commented out).
    """
    files = list(Path("common").rglob("*.[tT][xX][tT]"))
    for file in files:
        folder = file.parents[0]
        print(file)
        try:
            result = Extractor(file).data
        except:
            result = Extractor(file, pline=True).data # Let the Extractor print out lines to identify the faulty point
        result_folder = str(folder).replace("common", "common_json", 1)
        Path(result_folder).mkdir(parents=True, exist_ok=True)
        with open(str(file).replace('common\\', 'common_json\\').replace('.txt', '.json'), "w") as f:
            f.write(json.dumps(result, indent=4))