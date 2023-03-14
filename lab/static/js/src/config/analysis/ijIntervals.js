// The input consists of two positive integers, indicating the interval size
// in semitones and the interval size in scale steps.

/* global define: false */

define({
  "1/0": { label: "A1" }, // chromatic semitone
  "1/1": { label: "m2" }, // half step, diatonic semitone
  "2/1": { label: "M2" }, // whole step
  "3/1": { label: "A2" },
  "2/2": { label: "d3" },
  "3/2": { label: "m3" },
  "4/2": { label: "M3" },
  "5/2": { label: "A3" },
  "4/3": { label: "d4" },
  "5/3": { label: "P4" },
  "6/3": { label: "A4" }, // tritone
  "6/4": { label: "d5" }, // tritone
  "7/4": { label: "P5" },
  "8/4": { label: "A5" },
  "7/5": { label: "d6" }, // wolf fifth
  "8/5": { label: "m6" },
  "9/5": { label: "M6" },
  "10/5": { label: "A6" },
  "9/6": { label: "d7" },
  "10/6": { label: "m7" },
  "11/6": { label: "M7" },
  "11/7": { label: "d8" },
  "12/7": { label: "P8" }, // octave
  "13/7": { label: "A8" },
  "13/8": { label: "m9" },
  "14/8": { label: "M9" },
  "15/8": { label: "A9" },
  "14/9": { label: "d10" },
  "15/9": { label: "m10" },
  "16/9": { label: "M10" },
  "17/9": { label: "A10" },
  "16/10": { label: "d11" },
  "17/10": { label: "P11" },
  "18/10": { label: "A11" }, // tritone
  "18/11": { label: "d12" }, // tritone
  "19/11": { label: "P12" },
  "20/11": { label: "A12" },
  "19/12": { label: "d13" }, // wolf fifth
  "20/12": { label: "m13" },
  "21/12": { label: "M13" },
  "22/12": { label: "A13" },
  "21/13": { label: "d14" },
  "22/13": { label: "m14" },
  "23/13": { label: "M14" },
  "23/14": { label: "d15" },
  "24/14": { label: "P15" }, // double octave
  "25/14": { label: "A15" },
  "25/15": { label: "m16" },
  "26/15": { label: "M16" },
  "27/15": { label: "A16" },
  "26/16": { label: "d17" },
  "27/16": { label: "m17" },
  "28/16": { label: "M17" },
  "29/16": { label: "A17" },
  "28/17": { label: "d18" },
  "29/17": { label: "P18" },
  "30/17": { label: "A18" }, // tritone
  "30/18": { label: "d19" }, // tritone
  "31/18": { label: "P19" },
});
