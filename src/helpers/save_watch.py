"""
File containing the watch_save function.
"""
import os
import time
import shutil

def watch_save_job(target_file, destination_folder, stop_event, finish_event, queue, freq=1):
    """``watch_save`` in the (stop_event, finish_event, queue) protocol the GUI drives.

    The watcher runs until it is stopped, so ``finish_event`` fires on the way out
    rather than on completion. Module-level so it survives pickling under a spawn
    start method.
    """
    try:
        watch_save(target_file, destination_folder, stop_event, freq, queue)
    finally:
        finish_event.set()


def watch_save(target_file, destination_folder, stop_event, freq=1, queue=None):
    """
    Watch the autosave file and copy it to a designated folder whenever it is modified.

    ``queue``, when given, receives a 1 per copied autosave so a GUI can show a count.
    """
    # Get the initial modification time of the target file
    try:
        last_modified_time = os.path.getmtime(target_file)
    except FileNotFoundError:
        last_modified_time = None
    check = 0
    print("Save watcher watching")
    while not stop_event.is_set():
        # Wait for the specified interval before checking again
        time.sleep(1)
        # Check the current modification time
        try:
            current_modified_time = os.path.getmtime(target_file)

            # If the modification time has changed, copy the file
            if current_modified_time != last_modified_time:
                dest_path = f"autosave_{int(time.time())}.v3"
                if check % freq == 0:
                    shutil.copy(target_file, f"./saves/{destination_folder}/{dest_path}")
                    print(f"Copied {target_file} to {destination_folder}/{dest_path}")
                    if queue is not None:
                        queue.put(1)
                # Update the last modified time
                last_modified_time = current_modified_time
                check += 1
        except FileNotFoundError:
            continue
        except Exception as e:
            stop_event.set()
            raise RuntimeError(f"Error at SaveWatcher: {e}")
    print("Finished watching.")