""""
Interface to Rakaly save melter. The melter is available in Windows and Linux platforms
"""
import glob, subprocess, platform, os

def melt(address, out):
    if platform.system() == "Linux":
        envariables = os.environ.copy()
        envariables["LD_LIBRARY_PATH"] = "./bin/rakaly_linux/"
        command = ["./bin/rakaly_linux/melter", "save", address, out]
        with open(out, "w") as f:
            result = subprocess.run(
                command,
                stdout=f,
                stderr=subprocess.PIPE,
                text=True,
                env=envariables
        )
    elif platform.system() == "Windows":
        envariables = os.environ.copy()
        new_path = f"{os.path.abspath('./bin/rakaly_window/')};" + envariables["PATH"]
        envariables["PATH"] = new_path
        command = f'.\\bin\\rakaly_windows\\melter.exe save "{address}" "{out}"'
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True, env=envariables)

    else:
        raise NotImplementedError("Rakaly melter in other platforms is not available at the moment.")
    if result.returncode == 0:
        print(f"File {address} melted into {out}")
    else:
        print(result.stderr)
        print("Command failed with return code", result.returncode)
        raise ValueError("Command failed with return code", result.returncode)    


def melt_multiple(num, pattern):
    """
    Used to melt multiple files with a matching pattern at once.
    """
    files = glob.glob(pattern)
    out_files = []
    for i, file in enumerate(files):
        if num == i:
            break
    out_file = file.replace(".v3", ".txt")
    melt(file, out_file)
    out_files.append(out_file)
    return out_files