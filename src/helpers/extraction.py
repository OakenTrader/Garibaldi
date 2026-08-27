"""
File containing the save extraction functions
"""
from src.checkers.checkers_functions import rename_folder_to_date
from src.checkers.manager import (build_check_map, load_definitions,
                                    registered_checkers, required_topics, SaveManager)
import gc
from src.helpers.columnar import write_columns
from src.helpers.convert_localization import get_all_localization
from src.extractor import ExtractorSave
from src.helpers.melt import extract_native, melt
from src.helpers.utility import *
import time, shutil, re
from glob import glob


def _melt_and_extract(file, campaign_folder, delete):
    """Melt one input to blobs and return ``(save_folder, tree)``.

    ``file`` is a raw ``.v3``, a folder holding an already-melted ``save.txt``, or a
    folder extracted in an earlier session. In that last case the tree is ``None``
    and the folder is returned anyway, so its checkers run from the cached blobs.

    A ``.v3`` goes through the native extractor when one is installed, which melts
    and writes the blobs and columns in a single Rust process -- no ``save.txt``, no
    Python parse. It hands back no tree, so ``SaveManager`` reads the blobs, exactly
    as it does for a folder extracted in an earlier session. Whenever the extractor
    is absent or declines the save, the Python path below runs unchanged.

    Returns ``(None, None)`` when there is nothing to do. The folder is renamed to
    its save date here, so the returned path is final.
    """
    if ".v3" not in file: # an existing save folder
        if "save.txt" not in os.listdir(file):
            return file, None # already extracted -- check it from its blobs
        tree = extract_save_file(file)
        if delete:
            os.remove(f"{file}/save.txt")
        return file, tree

    folder = file.replace(".v3", "")
    os.makedirs(folder, exist_ok=True)

    tree = None
    if t_execute(extract_native)(file, folder) is None:
        try:
            t_execute(melt)(file, f"{folder}/save.txt")
        except NotImplementedError:
            return None, None
        except Exception as e:
            raise RuntimeError("Melting failed:", e)

        try:
            tree = extract_save_file(folder)
        except Exception as e:
            raise RuntimeError(f"Extraction of {file} failed: {str(e)}")

        os.remove(f"{folder}/save.txt")

    new_name = rename_folder_to_date(folder)
    if delete:
        os.remove(file)
    else:
        archived = f"./saves/{campaign_folder}/{new_name}.v3"
        os.rename(file, archived)
        shutil.move(archived, f"./saves/{campaign_folder}/archive/")
    return f"./saves/{campaign_folder}/{new_name}", tree


def parse_files(campaign_folder, files, checks, stop_event, finish_event, queue,
                delete=True, start_date=0, end_date=2024):
    """Melt, extract and check each save in one pass, handing the parsed tree
    straight to ``SaveManager`` instead of reading the blobs back.

    Two ordering rules hold here:

    * Blobs and columns are written before the checkers run, so nothing a checker
      attaches to a record ends up in the cache.
    * The date filter is applied after melting, since a raw
      ``autosave_<timestamp>.v3`` carries no date until melted. An out-of-range save
      is still extracted; only its checking is skipped.

    Signature matches ``extract_files`` / ``check_save_folders``, so the GUI's job
    runner drives it identically.
    """

    check_map = build_check_map()
    selected = {check_map[check][0] for check in checks}
    checkers = [c() for c in registered_checkers() if c in selected]
    # Game data is identical for every save, so it is read once per worker.
    definitions = load_definitions(checkers)
    localization = get_all_localization()

    if not delete:
        os.makedirs(f"./saves/{campaign_folder}/archive", exist_ok=True)
    try:
        for file in files:
            if stop_event.is_set():
                raise InterruptedError("Stop event set")
            if is_reserved_folder(file):
                continue

            save_folder, tree = _melt_and_extract(file, campaign_folder, delete)
            if save_folder is None:
                continue
            if stop_event.is_set():
                raise InterruptedError("Stop event set")

            # tree is None for a folder extracted earlier; SaveManager then reads
            # its blobs instead.
            date = date_from_folder_name(os.path.basename(save_folder.rstrip("/\\")))
            year_number = save_year_number(*date) if date else None
            if year_number is None or start_date <= year_number <= end_date + 1:
                if tree is not None:
                    # Drop every topic the checkers will not ask for, and collect,
                    # while this worker still holds the only reference.
                    keep = required_topics(checkers, save_folder)
                    tree = {topic: subtree for topic, subtree in tree.items()
                            if topic in keep}
                    gc.collect()
                save = SaveManager(save_folder, checkers, definitions, localization,
                                   save_data=tree)
                save.start_checking()
            tree = None
            gc.collect()
            queue.put(1)
    except Exception as e:
        stop_event.set()
        raise e
    finally:
        finish_event.set()

# Fully extract save file
def extract_save_file(save_file):
    """
    Handles extraction of a single save file.

    Returns the parsed tree so a caller that is about to check this save can use it
    directly instead of reading back the blobs just written (see ``parse_files``).
    Returns None on the debug-dump fallback, which produces no blobs.
    """
    try:
        data = t_execute(ExtractorSave)(f"{save_file}/save.txt")
        t_execute(data.write)(save_file, separate=True)
        write_columns(save_file, "pop", retrieve_from_tree(data.data, ["pops", "database"], null={}))
        return data.data
    except InterruptedError as e:
        raise InterruptedError("Stop event set")
    except Exception as e:
        data = ExtractorSave(f"{save_file}/save.txt", pline=True)
        return None

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

            # Native extractor first; see _melt_and_extract for why it may decline.
            if t_execute(extract_native)(file, folder) is None:
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
            if stop_event.is_set():
                raise InterruptedError("Stop event set")
            new_name = rename_folder_to_date(folder)
            if delete:
                os.remove(file)
            else:
                new_name = f"./saves/{campaign_folder}/{new_name}.v3"
                os.rename(file, new_name)
                shutil.move(new_name, f"./saves/{campaign_folder}/archive/")
            queue.put(1)
    except Exception as e:
        stop_event.set()
        raise e
    finally:
        finish_event.set()

