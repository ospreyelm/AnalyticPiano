HOW TO GENERATE EXERCISES

The exercise writing tool (writeExercise.sh) allows any users with access to a unix terminal to produce exercises for HarmonyLab with ease. This tool produces the .json files that HarmonyLab reads.

Instead of working through the prompts, users may prepare text files as illustrated in the file SAMPLE.txt and run the command `cat SAMPLE.txt | writeExercise.sh`.

LIMITATIONS

The supported MIDI pitch range is 21--108 (for output); the supported pitch classes are the 21 naturals, sharps, and flats, and B-double-flat, F-double-sharp, C-double-sharp, and G-double-sharp (for input); and all 30 major and minor keys are supported (for both input and output).

----------
April 2016, updated February 2018
RM

