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

Works for games in version 1.13.11
The program is not guaranteed to work in any other version (it will certainly break in earlier versions because Paradox changes variable names over time and I am too lazy to maintain backward compatibility)

The script is intended (atleast in the future) to be compatible with as many mods as possible and so we try not to hardcode any variable into the script, relying all data from the provided definition files

## Dependencies
Pandas, Numpy, Matplotlib, Zstandard, PySide6

## How to install and use
Either clone this repository (it now has everything you need) to use, or download from [here](https://github.com/OakenTrader/Garibaldi/releases/tag/v0.13.0)

After setup, press `run_linux.sh` or `run_windows.sh` to start the program.
1. Configure the program by giving it the location of the game `.../steam/steamapps/common/Victoria 3`, set the localization language, optionally add the folder containing the mods you play the game with (currently supports saves with only 1 mod at a time)
2. Accumulate save files during a game session by going to `Process`, select a folder to place all saves from a campaign. Then, browse for the location of the autosave file, and press start. The program will save the autosaves periodically to the campaign folder in `saves` folder as the game progresses.
3. After stopping, start parsing the files to extract the statistics. Adjust the number of threads to speed up the process. The graphs will be saved in `campaign_data` within the campaign folder, and statistics for individual saves can be viewed in respective subfolders.
4. You can also view the stats and graphs interactively.

The project is not polished yet (after years of free-time work). Do not hesitate to open an issue for bug reports and suggestions!

## Version 0.13.0
- GUI overhaul with Pyside6, with improved interactive graphs experience
- Several more statistics (income, expenses, companies)
- Implement the Rust version of save parser for even more speed
- Optimize the checking process