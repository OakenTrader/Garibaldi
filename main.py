from extractor import Extractor
from utility import get_size
from tech_tree import get_tech_tree
from check_innovation import check_innovation
from check_construction import check_construction
from check_infamy import check_infamy
import time

# Fully extract save file into json files
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
        data.dump_json("./saves/save_output", separate=True)
        print(f"{time.time() - t0} seconds")
    except:
        data = Extractor(save_file, True)

save_file = "./saves/autosave_1844.txt"
extract_save_file(save_file)
get_tech_tree(save_file)
check_innovation(save_file)
check_construction(save_file)
check_infamy(save_file)




