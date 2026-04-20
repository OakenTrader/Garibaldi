import zipfile, os
with zipfile.ZipFile("${zipPath}", "r") as zip_ref:
    zip_ref.extractall("${extractTo}")
print("Extracted files:", os.listdir("${extractTo}"))