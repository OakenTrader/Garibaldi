import sys, os, runpy

# Pfade richtig setzen
sys.path.extend([
    "${projectPath}",
    os.path.join("${projectPath}", "src"),
])

# Arbeitsverzeichnis ändern (wichtig!)
os.chdir("${projectPath}")

print("Current working dir:", os.getcwd())
print("Current working dir:", os.getcwd() +  "/src")
print("Files in root:", os.listdir(os.path.join(os.getcwd())))

# CLI-Argumente simulieren
sys.argv = ["web_extractSave.py", "Test"]

# Skript ausführen
runpy.run_path(os.path.join(os.path.join(os.getcwd()), "web_extractSave.py"), run_name="__main__")
print("Extraction Finished")
print("SAVE working dir:", os.getcwd() +  "/saves")
print("SAVE/TEST working dir:", os.getcwd() +  "/saves/Test")
print("Files in TEST:", os.listdir(os.path.join(os.getcwd() +  "/saves/Test")))