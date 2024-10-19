# Garibaldi: Victoria 3 Save Analyzer

Save game analyzer for Victoria 3 which retrieve information from autosaves across a campaign and plot them together.

## Features:
- Extract save files and retrieve/plot information of
    - Construction and average construction cost per point
    - Total and capped Innovation
    - Infamy
    - Prestige (consequently goods produced)
    - Technologies and table of technologies comparison
    - Population and literacy
- Watch the autosave file and copy it to a designated folder whenever it's changed
- View content of a save file (after extraction)

Save files must be in plaintext format. Rakaly's [`melter`](https://github.com/rakaly/librakaly) integrated in this program is available in Windows and Linux platforms and is executed on extraction.

Paradox definition files are required by the analyzers and **will not be provided** in the repository.

Works for games in version 1.7.6
The program is not guaranteed to work in any other version (it will certainly break in earlier versions because Paradox changes variable names over time and I am too lazy to maintain backward compatibility)

The script is intended (atleast in the future) to be compatible with as many mods as possible and so
we try not to hardcode any variable into the script, relying all data from the provided definition files

## Dependencies
Pandas, Numpy, Matplotlib
