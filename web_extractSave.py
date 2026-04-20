import sys
import glob
from src.helpers.extraction import extract_files

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_saves.py <campaign_folder>")
        sys.exit(1)

    campaign_folder = sys.argv[1]
    folders = glob.glob(f"./saves/{campaign_folder}/*.v3") + glob.glob(f"./saves/{campaign_folder}/*/")

    # Dummy-Objects
    class DummyEvent:
        def __init__(self): self._flag = False
        def set(self): self._flag = True
        def is_set(self): return self._flag

    class DummyQueue(list):
        def put(self, item): self.append(item)

    stop_event = DummyEvent()
    finish_event = DummyEvent()
    queue = DummyQueue()

    # RUN
    try:
        extract_files(campaign_folder, folders, stop_event, finish_event, queue, delete=False)
    except Exception as e:
        print(f"Errors while extracting: {e}")
        import traceback
        traceback.print_exc()

    print("Extraction finished.")
    print(f"Processed {len(queue)} files.")

if __name__ == "__main__":
    main()