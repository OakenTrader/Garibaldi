import os, micropip
if os.path.exists("${reqPath}"):
    with open("${reqPath}") as f:
        packages = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        print("Installing:", packages)
        await micropip.install(packages)
else:
    print("No requirements.txt found")