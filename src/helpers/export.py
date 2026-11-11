"""Export a campaign's parsed data as one zip, for sharing or analysis elsewhere."""

import os
import zipfile


def zip_campaign_data(campaign_folder):
    """Zip the csv and metadata files of ``saves/<campaign_folder>``, keeping the folder structure.

    Included: each save folder's ``metadata.json`` and every ``.csv`` in its ``data``
    subfolder. The zip is written to ``saves/<campaign_folder>/<campaign_folder>.zip``,
    replacing an earlier export.

    Returns ``(zip_path, file_count)``.
    """
    base_dir = os.path.join("saves", campaign_folder)
    zip_path = os.path.join(base_dir, f"{campaign_folder}.zip")
    count = 0
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for root, _dirs, files in os.walk(base_dir):
            if os.path.basename(root) == "data":
                wanted = [f for f in files if f.endswith(".csv")]
            else:
                # metadata.json only directly in a save folder, never from a nested one
                wanted = ["metadata.json"] if "metadata.json" in files else []
            for file in wanted:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, base_dir))
                count += 1
    return zip_path, count
