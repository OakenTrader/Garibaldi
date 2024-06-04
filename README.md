# Oaken's Victoria 3 files parser

My take on creating Victoria 3 File Parser. Based on observed patterns, the extractor.py is able to convert the save files and paradox moddable content files (stuffs in common and events folders) into a Python Dictionary ready to be worked on to get information on the save file.

From the extracted content, I have made scripts to obtain specific variables like the tech tree and construction of relevant nations. More to come.

Also in addition, the convert_localization.py generate a Python dictionary from localization files, again based on patterns of entries I want to get from the files.

## Dependencies
Pandas and Numpy
