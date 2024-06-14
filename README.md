# Garibaldi: Victoria 3 File Parser and Analyzer

My take on creating Victoria 3 File Parser. Based on observed patterns, the extractor.py is able to convert the save files and definition files (stuffs in common and events folders) into a Python Dictionary ready to be worked on to get information on the save file.

From the extracted content, I have made analyzer scripts to obtain specific variables like the tech tree and construction of relevant nations. More to come. 

Save files must be in plaintext format. Rakaly's [`melter`](https://github.com/rakaly/librakaly) is not integrated yet.

Paradox script files are required by the analyzers and **will not be provided** in the repository.

Also in addition, the convert_localization.py generate a Python dictionary from localization files, again based on patterns of entries I want to get from the files.

Works for games in version 1.5.13 and 1.6.2

The script is intended (atleast in the future) to be compatible with as many mods as possible and so
we try not to hardcode any variable into the script, relying all data from the provided definition files

## Dependencies
Pandas, Numpy, Matplotlib
