"""Command-line export: python export.py [campaign_folder]  (default: Colombia).

The same export is the Export button in the GUI's Process window."""
import sys

from src.helpers.export import zip_campaign_data

if __name__ == "__main__":
    path, count = zip_campaign_data(sys.argv[1] if len(sys.argv) > 1 else "Colombia")
    print(f"Created zip file: {path} ({count} files)")
