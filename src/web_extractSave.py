import sys
import glob
import multiprocessing
from helpers.extraction import extract_files

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_saves.py <campaign_folder>")
        sys.exit(1)
    campaign_folder = sys.argv[1]
    folders = glob.glob(f"./saves/{campaign_folder}/*.v3") + glob.glob(f"./saves/{campaign_folder}/*/")
    stop_event = multiprocessing.Event()
    finish_event = multiprocessing.Event()
    queue = multiprocessing.Queue()
    extract_files(campaign_folder, folders, stop_event, finish_event, queue, delete=False)
    print("Extraction finished.")

if __name__ == "__main__":
    main()
