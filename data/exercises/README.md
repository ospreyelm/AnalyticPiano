HOW TO GENERATE EXERCISES

The exercise writing tool (writeExercise.sh) allows any users with access to a unix terminal to produce exercises for HarmonyLab with ease. This tool produces the .json files that HarmonyLab reads. It also produces .ly (Lilypond) files which allow the exercises to be easily proof-read and printed in PDF format, but see the note below about the limited value of such previews.

Instead of working through the prompts, users may prepare text files as illustrated in the file SAMPLE.txt and run the command `cat SAMPLE.txt | writeExercise.sh`.

LIMITATIONS

The supported MIDI pitch range is 21--108 (for output); the supported pitch classes are the 21 naturals, sharps, and flats, and B-double-flat, F-double-sharp, C-double-sharp, and G-double-sharp (for input); and all 30 major and minor keys are supported (for both input and output).

LIMITED VALUE OF LILYPOND PREVIEW

The Lilypond preview does not include analytical annotations supplied by HarmonyLab. Nor does it allow the author to proof-read against enharmonic errors since HarmonyLab currently reads MIDI numbers, not note names, for exercises. Authors must create exercises consistent with HarmonyLab's ignorance of enharmonic difference on the input side, and they must be mindful of the currently supported melodic and harmonic entities. (Enharmonic spelling can only be so intelligent, when pitch combinations are assessed out of context.)

----------
April 2016
RM

