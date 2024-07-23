from scripts.extractor import Extractor
from scripts.helpers.melt import melt
from scripts.helpers.utility import *
from scripts.helpers.plotter import *
from scripts.checkers.tech_tree import check_tech_tree
from scripts.checkers.check_innovation import check_innovation
from scripts.checkers.check_construction import check_construction
from scripts.checkers.check_infamy import check_infamy
from scripts.checkers.check_prestige import *
import time, shutil
from glob import glob

# Fully extract save file
def extract_save_file(save_file):
    try:
        t0 = time.time()
        data = Extractor(f"{save_file}/save.txt")
        # print(f"Size: {get_size(data.data)}")
        print(f"{time.time() - t0} seconds")
        t0 = time.time()
        data.unquote()
        print(f"{time.time() - t0} seconds")
        t0 = time.time()
        data.write(save_file, separate=True)
        print(f"{time.time() - t0} seconds")
    except:
        data = Extractor(f"{save_file}/save.txt", True)

def extract_all_files(campaign_folder, stop_event, delete=True):
    """
    Melt and extract save files (all .v3 files in a campaign folder)
    """
    for file in glob(f"./saves/{campaign_folder}/*.v3"):
        folder = file.replace(".v3", "")
        try:
            os.mkdir(folder)
        except FileExistsError:
            continue
        try:
            melt(file, f"{folder}/save.txt")
        except NotImplementedError:
            shutil.move(file, folder)
            continue
        extract_save_file(f"{folder}")
        os.remove(f"{folder}/save.txt")
        if delete:
            os.remove(file)
    


    # Pre extracted save texts
    for folder in glob(f"./saves/{campaign_folder}/*/"):
        if "campaign_data" not in folder and "save.txt" in os.listdir(folder):
            extract_save_file(f"{folder}")
            if delete:
                os.remove(f"{folder}/save.txt")

    rename_folder_to_date(campaign_folder)

    plot_stat(campaign_folder, "construction", check_construction, input_file="construction.csv", limit="players", reset=0, title="Construction", save_name="construction")
    plot_stat(campaign_folder, "innovation", check_innovation, input_file="innovation.csv", reset=0, limit="players", title="Total Innovation", save_name="innovation")
    plot_stat(campaign_folder, "capped_innovation", check_innovation, input_file="innovation.csv", reset=0, limit="players", title="Capped Innovation", save_name="capped_innovation")
    plot_stat(campaign_folder, "infamy", check_infamy, reset=0, limit="players")
    for column in prestige_columns:
        plot_stat(campaign_folder, column, check_prestige, input_file="prestige.csv", reset=0, limit="players")
    plot_goods_produced(campaign_folder)
    plot_stat(campaign_folder, "total", check_prestige, input_file="prestige.csv", reset=0, limit="players", title="Total Prestige", save_name="total_prestige")
    for folder in glob(f"./saves/{campaign_folder}/{campaign_folder}*"):
        try:
            check_tech_tree(folder)
        except:
            continue
    plot_stat(campaign_folder, "avg_cost", check_construction, input_file="construction.csv", limit="players", reset=0, title="Average Construction cost", save_name="avg_construction", show=True)