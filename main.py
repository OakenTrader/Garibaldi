from scripts.extractor import Extractor
from scripts.helpers.utility import *
from scripts.helpers.plotter import *
from scripts.checkers.tech_tree import get_tech_tree
from scripts.checkers.check_innovation import check_innovation
from scripts.checkers.check_construction import check_construction
from scripts.checkers.check_infamy import check_infamy
import time

# Fully extract save file
def extract_save_file(save_file):
    try:
        t0 = time.time()
        data = Extractor(f"{save_file}/save.txt")
        print(f"Size: {get_size(data.data)}")
        print(f"{time.time() - t0} seconds")
        t0 = time.time()
        data.unquote()
        print(f"{time.time() - t0} seconds")
        t0 = time.time()
        data.write(save_file, separate=True)
        print(f"{time.time() - t0} seconds")
    except:
        data = Extractor(save_file, True)


sample_save = "./saves/campaign_folder/save_folder"
extract_save_file(sample_save)
check_construction(sample_save)
check_infamy(sample_save)
check_innovation(sample_save)
get_tech_tree(sample_save)
campaign_folder = "campaign_folder" # No ./saves
plot_stat(campaign_folder, "construction", check_construction, input_file="construction.csv", player_only=True, reset=True)
plot_stat(campaign_folder, "innovation", check_innovation, reset=True, player_only=False)
plot_stat(campaign_folder, "infamy", check_infamy, reset=True, player_only=True)

