""""
Interface to Rakaly save melter. The melter is available in Windows and Linux platforms
"""
import glob, json, subprocess, platform, os

# The native extractor melts and writes extracted_save/ + columns/ in one process,
# replacing melt + ExtractorSave + Extractor.write + write_columns. Built from
# librakaly-melter/extractor/ and installed beside the melter it links.
NATIVE_EXTRACTOR = {
    "Linux": "./bin/rakaly_linux/vic3-extract",
    "Windows": "./bin/rakaly_windows/vic3-extract.exe",
}
# The extractor's own exit code for "this save needs the Python parser": it hit
# something -- non-UTF-8 output, a non-ASCII space -- where its byte-level
# splitting would not agree with Python's str.split().
_EXIT_USE_PYTHON = 3


def native_extractor():
    """Path to the native extractor, or None when it is not available here."""
    path = NATIVE_EXTRACTOR.get(platform.system())
    if path is None or not os.path.exists(path):
        return None
    if os.environ.get("GARIBALDI_NATIVE_EXTRACT", "1") == "0":
        return None
    return path


def extract_native(address, save_folder, schema="./src/save_schema.toml"):
    """Melt and extract ``address`` into ``save_folder`` with the native extractor.

    Returns the run's JSON summary, or None when the extractor is unavailable or
    handed the save back (exit code 3) -- in both cases the caller falls back to
    melt + ``ExtractorSave``. Raises on a real failure, which must not be silently
    swallowed: a save that half-extracted would leave a corrupt blob directory.
    """
    binary = native_extractor()
    if binary is None:
        return None
    result = subprocess.run(
        [binary, address, save_folder, "--schema", schema],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if result.returncode == _EXIT_USE_PYTHON:
        print(f"{binary}: {result.stderr.strip()} -- falling back to the Python parser")
        return None
    if result.returncode != 0:
        raise RuntimeError(f"{binary} exited {result.returncode}: {result.stderr.strip()}")
    try:
        summary = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"{binary} produced no summary: {result.stdout[:200]!r}")
    # melt.py's own weakness, closed here: the melter returns 0 even when tokens are
    # missing from its table, so a stale table used to feed __unknown_0x keys into
    # the checkers silently.
    if summary.get("unknown_tokens"):
        print(f"WARNING {address}: melted with unknown tokens -- the token table is "
              f"stale for this game version; re-run librakaly-melter/build.sh")
    for note in summary.get("column_notes", []):
        print(f"Column cache note ({note}); the dict path still applies")
    print(f"File {address} extracted into {save_folder} "
          f"({summary['seconds']['total']:.1f}s)")
    return summary


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