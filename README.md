# Garibaldi: Victoria 3 Save Analyzer

Save game analyzer for Victoria 3 which retrieve information from autosaves across a campaign and plot them together. The script is designed for campaigns in multiplayer (also works for singleplayer campaigns) and is run on Python.

## Features:
- Extract save files and retrieve/plot information of
    - Construction and average construction cost per point
    - Total and capped Innovation
    - Infamy
    - Prestige (consequently goods produced)
    - Technologies and table of technologies comparison
    - Demographics, including Standard of Living
    - Finance, including GDP, money and debt
- Watch the autosave file and copy it to a designated folder whenever it's changed
- View content of a save file (after extraction)

The script utilizes Rakaly's [`melter`](https://github.com/rakaly/librakaly), shipped in the release zip file, which allows a smooth pipeline of
    - Automatically dumping autosaves in a designated folder during a game session
    - Mass melting dumped autosaves after session
    - Completing the data processing to get readable statistics and graphs

The melter integrated in this program is available in Windows and Linux platforms and is executed on extraction.

Paradox definition files are required by the analyzers and **will not be provided** in the repository.

Works for games in version 1.10
The program is not guaranteed to work in any other version (it will certainly break in earlier versions because Paradox changes variable names over time and I am too lazy to maintain backward compatibility)

The script is intended (atleast in the future) to be compatible with as many mods as possible and so we try not to hardcode any variable into the script, relying all data from the provided definition files

## Dependencies
Pandas, Numpy, Matplotlib

## How to install and use
Refer to https://github.com/OakenTrader/Garibaldi/issues/1 for Windows users who are not familiar with Python for installation as well as usage instructions.

The project is still far from polished. File extraction is around 30-60 seconds per save, the analyzing process is not truly optimized, and some statistics may not be correct (radicals/loyalists certainly are). Do not hesitate to open an issue for bug reports and suggestions!

## Version 0.10.0
Either clone this repository (it now has everything you need) to use, or download from [here](https://github.com/OakenTrader/Garibaldi/releases/tag/v0.10.0)
- Update to 1.10 games
- Some project restructuring (again) and bugfixes
