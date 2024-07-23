""""
Interface to Rakaly save melter. Currently only available for programs running on Linux platform because I can't figure out how to compile the melter for Windows platform.
"""
import glob, subprocess, platform

def melt(address, out):
    if platform.system() == "Linux":
        command = f'./saves/melter save {address} > {out}'
        envariables = {'LD_LIBRARY_PATH': "./saves/"}
    else:
        raise NotImplementedError("Rakaly melter in other platforms is not available at the moment. The file is now moved inside the folder.")
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