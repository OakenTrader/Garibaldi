from extractor import Extractor
from utility import get_size
from tech_tree import get_tech_tree
from check_construction import check_construction
from check_infamy import check_infamy
from check_construction import check_innovation
import time

# Example extraction with a save file
def extract_save_file(save_file):
    try:
        t0 = time.time()
        data = Extractor(save_file)
        print(f"Size: {get_size(data.data)}")
        print(f"{time.time() - t0} seconds")
        t0 = time.time()
        data.unquote()
        print(f"{time.time() - t0} seconds")
        t0 = time.time()
        data.dump_json("./save files/save_output", separate=True)
        print(f"{time.time() - t0} seconds")
    except:
        data = Extractor(save_file, True)

get_tech_tree("./save files/1865.v3")
check_infamy()
check_construction()
check_innovation()




