"use strict";
var mod = require("./note_entry_gate_logic");

var pass = 0, fail = 0;
function assertEqual(name, got, want) {
  if (got === want) { pass++; console.log("ok - " + name); }
  else { fail++; console.error("FAIL - " + name + " got:" + got + " want:" + want); }
}

assertEqual("suspend when INPUT focused", mod.shouldSuspendNoteEntry("INPUT", "text"), true);
assertEqual("suspend when TEXTAREA focused", mod.shouldSuspendNoteEntry("TEXTAREA", null), true);
assertEqual("suspend when contenteditable", mod.shouldSuspendNoteEntry("DIV", null, true), true);
assertEqual("do not suspend for checkbox input", mod.shouldSuspendNoteEntry("INPUT", "checkbox"), false);
assertEqual("do not suspend for body", mod.shouldSuspendNoteEntry("BODY", null), false);
assertEqual("do not suspend when nothing focused", mod.shouldSuspendNoteEntry(null, null), false);

if (fail > 0) { console.error("\n" + fail + " failed."); process.exit(1); }
else { console.log("\nAll note_entry_gate_logic assertions passed (" + pass + ")."); }
