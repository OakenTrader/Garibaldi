import os
import time
import shutil

def watch_save(target_file, destination_folder, freq=1, interval=5):
    """
    Watch the autosave file and copy it to a designated folder whenever it is modified.
    """
    # Get the initial modification time of the target file
    last_modified_time = os.path.getmtime(target_file)
    check = 0
    try:
        print("Save watcher watching")
        while True:
            # Wait for the specified interval before checking again
            time.sleep(interval)
            # Check the current modification time
            try:
                current_modified_time = os.path.getmtime(target_file)

                # If the modification time has changed, copy the file
                if current_modified_time != last_modified_time:
                    print(f"{target_file} has been modified")
                    dest_path = f"autosave_{int(time.time())}.v3"
                    if check % freq == 0:
                        shutil.copy(target_file, f"{destination_folder}/{dest_path}")
                        print(f"Copied {target_file} to {destination_folder}/{dest_path}")
                    # Update the last modified time
                    last_modified_time = current_modified_time
                    check += 1
            except FileNotFoundError:
                print("File missing at the moment")
                continue

    except KeyboardInterrupt:
        print("Stopping file observer")