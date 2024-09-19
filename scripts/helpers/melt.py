""""
Interface to Rakaly save melter. The melter is available in Windows and Linux platforms
"""
import glob, subprocess, platform, os

def melt(address, out):
    if platform.system() == "Linux":
        command = f'./bin/rakaly_linux/melter save {address} > {out}'
        envariables = {'LD_LIBRARY_PATH': "./bin/rakaly_linux/"}
    elif platform.system() == "Windows":
        envariables = os.environ.copy()
        new_path = f"{os.path.abspath('./bin/rakaly_window/')};" + envariables["PATH"]
        envariables["PATH"] = new_path
        command = f'.\\bin\\rakaly_windows\\melter.exe save {address} {out}'
    else:
        raise NotImplementedError("Rakaly melter in other platforms is not available at the moment.")
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True, env=envariables)
    print(result.stdout)
    print(result.stderr)
    # Check if the command was executed successfully
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