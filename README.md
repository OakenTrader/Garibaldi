# Garibaldi: Victoria 3 File Parser and Analyzer

My take on creating Victoria 3 File Parser. Based on observed patterns, the extractor.py is able to convert the save files and definition files (stuffs in common and events folders) into a Python Dictionary ready to be worked on to get information on the save file.

From the extracted content, I have made analyzer scripts to obtain specific variables like the tech tree and construction of relevant nations. More to come. 

## Features:
- Extract save files and retrieve/plot information of
    - Construction and average construction cost per point
    - Total and capped Innovation
    - Infamy
    - Prestige (consequently goods produced)
    - Number of researched technologies and technologies each nation have missed
- Watch the autosave file and copy it to a designated folder whenever it's changed
- View content of a save file (after extraction)

Save files must be in plaintext format. Rakaly's [`melter`](https://github.com/rakaly/librakaly) integrated in this program is available in Windows and Linux platforms and is executed on extraction.

Paradox definition files are required by the analyzers and **will not be provided** in the repository.

Works for games in version 1.5.13, 1.6.2, 1.7 and hopefully whatever in between.
(Variables name in save files change with version and I'm not totally sure I've handled all such changes so please open an issue whenever there is an error.)

The script is intended (atleast in the future) to be compatible with as many mods as possible and so
we try not to hardcode any variable into the script, relying all data from the provided definition files

## Dependencies
Pandas, Numpy, Matplotlib
