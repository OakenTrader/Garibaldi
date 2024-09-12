"""
File containing the save extraction functions
"""
from scripts.checkers.checkers_functions import rename_folder_to_date
from scripts.extractor import Extractor
from scripts.helpers.melt import melt
from scripts.helpers.utility import *
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

def extract_all_files(campaign_folder, stop_event, delete=True):
    """
    Melt and extract save files (all .v3 files in a campaign folder)
    If analyze is set to False the function watch for a melted .txt file and readily extract it when one appear.
    """
    if not delete:
        try:
            os.mkdir(f"./saves/{campaign_folder}/archive")
        except FileExistsError:
            pass
    try:
        while not stop_event.is_set():
            time.sleep(1)
            files = glob(f"./saves/{campaign_folder}/*.v3")
            number = len(files)
            done = 0
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
                done += 1
                print("Progress")
                rename_folder_to_date(folder)
        
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
            

    except Exception as e:
        raise e
    finally:
        stop_event.set()