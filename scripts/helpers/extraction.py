"""
File containing the save extraction functions
"""
from scripts.extractor import Extractor
from scripts.helpers.melt import melt
from scripts.helpers.utility import *
from scripts.helpers.plotter import *
from scripts.checkers.tech_tree import check_tech_tree
from scripts.checkers.check_innovation import check_innovation
from scripts.checkers.check_construction import check_construction
from scripts.checkers.check_infamy import check_infamy
from scripts.checkers.check_prestige import *
import time, shutil, re
from glob import glob

# Fully extract save file
def extract_save_file(save_file, stop_event):
    """
    Handles extraction of a single save file.
    """
    try:
        data = t_execute(Extractor)(f"{save_file}/save.txt", is_save=True, stop_event=stop_event)
        t_execute(data.unquote)()
        t_execute(data.write)(save_file, separate=True)
    except InterruptedError as e:
        raise InterruptedError("Stop event set")
    except Exception as e:
        data = Extractor(f"{save_file}/save.txt", is_save=True, pline=True, stop_event=stop_event)

def extract_all_files(campaign_folder, stop_event, delete=True, analyze=False):
    """
    Melt and extract save files (all .v3 files in a campaign folder)
    If analyze is set to False the function watch for a melted .txt file and readily extract it when one appear.
    """
    try:
        if not delete:
            try:
                os.mkdir(f"./saves/{campaign_folder}/archive")
            except FileExistsError:
                pass
        while not stop_event.is_set():
            time.sleep(1)
            for file in glob(f"./saves/{campaign_folder}/*.v3"):
                folder = file.replace(".v3", "")
                try:
                    os.mkdir(folder)
                except FileExistsError:
                    continue
                try:
                    t_execute(melt)(file, f"{folder}/save.txt")
                except NotImplementedError:
                    shutil.move(file, folder)
                    continue
                except Exception as e:
                    raise RuntimeError("Melting failed:", e)
                if stop_event.is_set():
                    raise InterruptedError("Stop event set")
                try:
                    extract_save_file(folder, stop_event)
                except Exception as e:
                    raise RuntimeError(f"Extraction of {file} failed: {str(e)}")
                os.remove(f"{folder}/save.txt")
                if delete:
                    os.remove(file)
                else:
                    shutil.move(file, f"./saves/{campaign_folder}/archive")
            if analyze:
                break
        
        """Melt and extract .v3 in non-archive folders"""
        for file in glob(f"./saves/{campaign_folder}/*/*.v3"):
            if stop_event.is_set():
                raise InterruptedError("Stop event set")
            folder = './' + '/'.join(re.split(r"[/\\]", file)[1:-1])
            if is_reserved_folder(folder):
                continue
            t_execute(melt)(file, f"{folder}/save.txt")
            try:
                extract_save_file(folder, stop_event)
            except Exception as e:
                raise RuntimeError(f"Extraction of {file} failed: {str(e)}")
            os.remove(f"{folder}/save.txt")
            if delete:
                os.remove(file)
            else:
                shutil.move(file, f"./saves/{campaign_folder}/archive")

        # Pre extracted save texts
        for folder in glob(f"./saves/{campaign_folder}/*/"):
            if stop_event.is_set():
                raise InterruptedError("Stop event set")
            if is_reserved_folder(folder):
                continue
            if "save.txt" in os.listdir(folder):
                extract_save_file(f"{folder}", stop_event)
                if delete:
                    os.remove(f"{folder}/save.txt")

        # Rename folders
        for folder in glob(f"./saves/{campaign_folder}/*/"):
            if stop_event.is_set():
                raise InterruptedError("Stop event set")
            if is_reserved_folder(folder):
                continue
            rename_folder_to_date(folder)

        if analyze:
            full_analyze(campaign_folder)

    except Exception as e:
        raise e
    finally:
        stop_event.set()

def full_analyze(campaign_folder):
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
"""
FIXME showing pyplots in a threaded function will cause undesired effects on thread and GUI
"""