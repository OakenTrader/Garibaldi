import os
import time
import shutil

def observe_file(target_file, destination_folder, interval=5):
    """
    Watch the autosave file and copy it to a designated folder whenever it is modified.
    """
    # Get the initial modification time of the target file
    last_modified_time = os.path.getmtime(target_file)

    try:
        while True:
            # Wait for the specified interval before checking again
            time.sleep(interval)
            # Check the current modification time
            try:
                current_modified_time = os.path.getmtime(target_file)

                # If the modification time has changed, copy the file
                if current_modified_time != last_modified_time:
                    print(f"{target_file} has been modified")
                    base, ext = os.path.splitext(destination_folder)
                    dest_path = f"{base}_{int(time.time())}{ext}"
                    shutil.copy(target_file, dest_path)
                    print(f"Copied {target_file} to {dest_path}")

                    # Update the last modified time
                    last_modified_time = current_modified_time
            except FileNotFoundError:
                print("File missing at the moment")
                continue

    except KeyboardInterrupt:
        print("Stopping file observer")