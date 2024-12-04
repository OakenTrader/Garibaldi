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
def extract_save_file(save_file):
    """
    Handles extraction of a single save file.
    """
    try:
        data = t_execute(Extractor)(f"{save_file}/save.txt", is_save=True)
        t_execute(data.unquote)()
        t_execute(data.write)(save_file, separate=True)
    except InterruptedError as e:
        raise InterruptedError("Stop event set")
    except Exception as e:
        data = Extractor(f"{save_file}/save.txt", is_save=True, pline=True)

def extract_files(campaign_folder, files, stop_event, finish_event, queue, delete=True):
    """
    Melt and extract save files (all .v3 files in a campaign folder and pre-melted save texts)
    Arguments:
        - campaign_folder (str) : Name of the target folder in the save folder
        - files (list[str]) : List of files path to extract
        - stop_event (multiprocessing.Event) : To communicate termination of the process with the GUI
        - finish_event (multiprocessing.Event) : To be set if the extraction is completed without exception
        - queue (multiprocessing.Queue) : To communicate progress with the main thread
    """
    if not delete:
        try:
            os.mkdir(f"./saves/{campaign_folder}/archive")
        except FileExistsError:
            pass
    try:
        for file in files:
            if stop_event.is_set():
                raise InterruptedError("Stop event set")
            if is_reserved_folder(file):
                continue
            if ".v3" not in file: # check pre-extracted saves
                if "save.txt" in os.listdir(file):
                    extract_save_file(f"{file}")
                    if delete:
                        os.remove(f"{file}/save.txt")
                continue
            folder = file.replace(".v3", "")

            try:
                os.mkdir(folder)
            except FileExistsError:
                pass

            try:
                t_execute(melt)(file, f"{folder}/save.txt")
            except NotImplementedError:
                continue
            except Exception as e:
                raise RuntimeError("Melting failed:", e)
            if stop_event.is_set():
                raise InterruptedError("Stop event set")
            
            try:
                extract_save_file(folder)
            except Exception as e:
                raise RuntimeError(f"Extraction of {file} failed: {str(e)}")
            
            os.remove(f"{folder}/save.txt")
            if delete:
                os.remove(file)
            else:
                shutil.move(file, f"./saves/{campaign_folder}/archive/")
            rename_folder_to_date(folder)
            queue.put(1)
    except Exception as e:
        stop_event.set()
        raise e
    finally:
        finish_event.set()

