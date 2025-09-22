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

Save files must be in plaintext format. Rakaly's [`melter`](https://github.com/rakaly/librakaly) integrated in this program is available in Windows and Linux platforms and is executed on extraction.

Paradox definition files are required by the analyzers and **will not be provided** in the repository.

Works for games in version 1.9
The program is not guaranteed to work in any other version (it will certainly break in earlier versions because Paradox changes variable names over time and I am too lazy to maintain backward compatibility)

The script is intended (atleast in the future) to be compatible with as many mods as possible and so
we try not to hardcode any variable into the script, relying all data from the provided definition files

## Dependencies
Pandas, Numpy, Matplotlib

## How to install and use
Refer to https://github.com/OakenTrader/Garibaldi/issues/1 for Windows users who are not familiar with Python for installation as well as usage instructions.

Do not hesitate to open an issue for bug reports and suggestions!

## Version 0.9.0
Windows users download the rar file from [here](https://github.com/OakenTrader/Garibaldi/releases/tag/v0.9.0)
- Restructured script structure
- Statistics of all countries are now saved in extracted_save folder of each save, while the old stat csv files will only show player countries
- More convenient mod selection
- Slight Optimization
- Added a few more statistics (GDP per capita, standard of living and innovation ratio over cap)