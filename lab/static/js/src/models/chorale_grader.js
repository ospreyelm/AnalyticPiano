/* global define: false */
define([
  "lodash",
  "app/components/music/score_timeline",
], function (_, ScoreTimeline) {
  "use strict";

  var INCORRECT = "incorrect";
  var CORRECT = "correct";
  var PARTIAL = "partial";

  function groupByOnset(timeline) {
    var groups = [];
    var onsetToIndex = Object.create(null);
    for (var i = 0; i < timeline.length; i++) {
      var ev = timeline[i];
      if (!(ev.onset in onsetToIndex)) {
        onsetToIndex[ev.onset] = groups.length;
        groups.push([]);
      }
      groups[onsetToIndex[ev.onset]].push(i);
    }
    return { groups: groups, onsetToIndex: onsetToIndex };
  }

  var ChoraleGrader = function (settings) {
    this.settings = settings || {};
    this.reset();
  };

  ChoraleGrader.STATE = {
    INCORRECT: INCORRECT,
    CORRECT: CORRECT,
    PARTIAL: PARTIAL,
  };

  _.extend(ChoraleGrader.prototype, {
    STATE: ChoraleGrader.STATE,

    reset: function () {
      this.timeline = [];
      this.windowGroups = []; // array of arrays of timeline indices per onset
      this.pointer = 0; // window index
      this.playedNoteIds = new Set();
      this.heldMidi = new Set();
      this.mistakeMade = false; // sticky overall flag
      this._lastIncorrect = false; // one-shot flag for grading INCORRECT
      this.finished = false;
    },

    initFromDefinition: function (definition) {
      this.reset();
      var score = definition.getScore ? definition.getScore() : null;
      if (!score) return this;

      console.log("[INIT] Score has " + (score.measures ? score.measures.length : 0) + " measures");

      this.timeline = ScoreTimeline.buildTimeline(score);
      var g = groupByOnset(this.timeline);
      var rawGroups = g.groups;

      // Merge windows that are close together (within 1024 ticks = 1 beat)
      // This groups passing tones with their beat-aligned chords
      this.windowGroups = [];
      var mergedGroup = [];
      var lastOnset = null;

      for (var w = 0; w < rawGroups.length; w++) {
        var groupIndices = rawGroups[w];
        var onset = this.timeline[groupIndices[0]].onset;

        // If this is the first group or onset is close to last (within 1 beat), merge
        if (lastOnset === null || (onset - lastOnset <= 1024)) {
          mergedGroup = mergedGroup.concat(groupIndices);
          lastOnset = onset;
        } else {
          // Save the merged group and start a new one
          this.windowGroups.push(mergedGroup);
          mergedGroup = groupIndices.slice();
          lastOnset = onset;
        }
      }
      // Don't forget the last group
      if (mergedGroup.length > 0) {
        this.windowGroups.push(mergedGroup);
      }

      console.log("[INIT] Merged " + rawGroups.length + " onset groups into " + this.windowGroups.length + " windows");

      this.pointer = 0;
      this.finished = this.windowGroups.length === 0;
      
      // Log timeline summary with measure coverage
      var measureCounts = {};
      for (var i = 0; i < this.timeline.length; i++) {
        var m = this.timeline[i].measureIndex;
        measureCounts[m] = (measureCounts[m] || 0) + 1;
      }
      console.log("[INIT] Built timeline with " + this.timeline.length + " events across " + this.windowGroups.length + " onset windows");
      console.log("[INIT] Events per measure:", measureCounts);
      console.log("[INIT] First 5 windows:", this.windowGroups.slice(0, 5).map(function(idxs, winIdx) {
        var tl = this.timeline;
        var onset = tl[idxs[0]].onset;
        var midis = idxs.map(function(i) { return tl[i].midi; });
        return "Window " + winIdx + " (onset=" + onset + "): " + midis.join(", ");
      }.bind(this)));
      console.log("[INIT] Windows 8-12 (where you might get stuck):", this.windowGroups.slice(8, 13).map(function(idxs, relIdx) {
        var winIdx = relIdx + 8;
        var tl = this.timeline;
        var onset = tl[idxs[0]].onset;
        var details = idxs.map(function(i) {
          return "midi=" + tl[i].midi + " staff=" + tl[i].staff + " voice=" + tl[i].voiceIndex;
        });
        var measure = tl[idxs[0]].measureIndex;
        return "Window " + winIdx + " (measure=" + measure + ", onset=" + onset + "): [" + details.join("; ") + "]";
      }.bind(this)));

      // Enhanced logging for last measure tracking
      if (score.measures && score.measures.length > 0) {
        var lastMeasureIdx = score.measures.length - 1;
        var lastMeasureEvents = this.timeline.filter(function(ev) {
          return ev.measureIndex === lastMeasureIdx;
        });
        console.log("[INIT] Last measure (index=" + lastMeasureIdx + ") has " +
                    lastMeasureEvents.length + " events");

        // Find windows containing last measure
        var lastMeasureWindows = [];
        for (var w = 0; w < this.windowGroups.length; w++) {
          var idxs = this.windowGroups[w];
          for (var i = 0; i < idxs.length; i++) {
            if (this.timeline[idxs[i]].measureIndex === lastMeasureIdx) {
              lastMeasureWindows.push(w);
              break;
            }
          }
        }
        console.log("[INIT] Last measure appears in windows:", lastMeasureWindows);
      }

      return this;
    },

    getPlayedNoteIds: function () {
      // Return the live Set so renderer can use .has()
      return this.playedNoteIds;
    },

    getActiveIndex: function () {
      return this.pointer;
    },
    
    getActiveMeasureIndex: function () {
      if (!this.timeline.length || !this.windowGroups.length) {
        return 0;
      }
      var pointer = this.pointer;
      if (pointer >= this.windowGroups.length) {
        pointer = this.windowGroups.length - 1;
      }
      if (pointer < 0) {
        return 0;
      }
      var idxs = this.windowGroups[pointer];
      if (!idxs || !idxs.length) {
        var lastEvent = this.timeline[this.timeline.length - 1];
        return lastEvent && typeof lastEvent.measureIndex === "number"
          ? lastEvent.measureIndex
          : 0;
      }
      var evt = this.timeline[idxs[0]];
      return evt && typeof evt.measureIndex === "number" ? evt.measureIndex : 0;
    },

    // Feed MIDI events
    noteOn: function (midi) {
      console.log("[1. PLAY] NOTE ON:", midi);
      
      if (this.finished) return;
      this.heldMidi.add(midi);

      // Match against current window only
      var tl = this.timeline;
      if (this.pointer >= this.windowGroups.length) return;
      var idxs = this.windowGroups[this.pointer];

      // Current window details
      var windowMidis = idxs.map(function(idx) { return tl[idx].midi; });
      var windowOnset = tl[idxs[0]].onset;
      
      // Find held notes: look back for the most recent event per voice that's still sounding
      var heldNotes = this._getHeldNotesAtOnset(windowOnset);
      var allExpected = windowMidis.concat(heldNotes.map(function(ev) { return ev.midi; }));
      console.log("[2. GRADE] Current window onset=" + windowOnset +
                  ", new attacks:", windowMidis,
                  ", held notes:", heldNotes.map(function(e) {
                    return "midi=" + e.midi + " (onset=" + e.onset + ", dur=" + e.duration + ")";
                  }),
                  ", all expected:", allExpected);

      // Attempt to match any unplayed event in window by MIDI
      var matched = false;
      for (var i = 0; i < idxs.length; i++) {
        var ev = tl[idxs[i]];
        if (!this.playedNoteIds.has(ev.id) && ev.midi === midi) {
          this.playedNoteIds.add(ev.id);
          matched = true;
          console.log("[2. GRADE] ✓ Matched note " + midi + " in current window (id=" + ev.id + ")");
          break;
        }
      }

      // Also check held notes
      if (!matched) {
        for (var j = 0; j < heldNotes.length; j++) {
          if (!this.playedNoteIds.has(heldNotes[j].id) && heldNotes[j].midi === midi) {
            this.playedNoteIds.add(heldNotes[j].id);
            matched = true;
            console.log("[2. GRADE] ✓ Matched held note " + midi + " (id=" + heldNotes[j].id + ")");
            break;
          }
        }
      }


      if (!matched) {
        // Wrong note for this window
        this.mistakeMade = true;
        this._lastIncorrect = true; // one-shot INCORRECT
        console.log("[2. GRADE] ✗ Wrong note " + midi + " for current window");
      }

      // Check if current window is now complete and advance
      var oldPointer = this.pointer;
      this._advanceIfWindowComplete();
      if (this.pointer !== oldPointer) {
        console.log("[3. VISUAL] Advanced window pointer from " + oldPointer + " to " + this.pointer);
      }
    },
    
    // Find notes that are still sounding at a given onset (from previous events)
    _getHeldNotesAtOnset: function(onset) {
      var tl = this.timeline;
      var held = [];
      var voiceSeen = {}; // track which voice/staff combos we've seen
      
      // Walk backwards through timeline to find most recent event per voice before this onset
      for (var i = tl.length - 1; i >= 0; i--) {
        var ev = tl[i];
        if (ev.onset >= onset) continue; // skip events at or after current onset
        
        var key = ev.staff + "_" + ev.voiceIndex;
        if (voiceSeen[key]) continue; // already found most recent for this voice
        
        // Check if this note is still sounding at the target onset
        if (ev.onset + ev.duration > onset) {
          held.push(ev);
        }
        // ALWAYS mark voice as seen after checking first occurrence before onset
        voiceSeen[key] = true;
      }

      return held;
    },

    noteOff: function (midi) {
      console.log("[1. PLAY] NOTE OFF:", midi);
      // Only track release. No advancement required on release.
      if (this.heldMidi.has(midi)) this.heldMidi.delete(midi);
    },

    _advanceIfWindowComplete: function () {
      var tl = this.timeline;
      var safety = 0;
      while (this.pointer < this.windowGroups.length && safety < 1024) {
        var idxs = this.windowGroups[this.pointer];
        var onset = tl[idxs[0]].onset;
        
        // Include held notes in completion check
        var heldNotes = this._getHeldNotesAtOnset(onset);
        var allRequired = idxs.concat(heldNotes.map(function(ev) { return tl.indexOf(ev); }).filter(function(idx) { return idx !== -1; }));
        
        // Is current window complete (all new attacks + held notes played)?
        var windowDone = true;
        var playedCount = 0;
        for (var i = 0; i < idxs.length; i++) {
          if (this.playedNoteIds.has(tl[idxs[i]].id)) {
            playedCount++;
          } else {
            windowDone = false;
          }
        }
        for (var h = 0; h < heldNotes.length; h++) {
          if (this.playedNoteIds.has(heldNotes[h].id)) {
            playedCount++;
          } else {
            windowDone = false;
          }
        }
        
        var totalRequired = idxs.length + heldNotes.length;
        console.log("[2. GRADE] Window check: played " + playedCount + "/" + totalRequired + " notes (" + idxs.length + " new + " + heldNotes.length + " held), complete=" + windowDone);
        
        if (!windowDone) break;

        // Move to next window
        var oldPointer = this.pointer;
        this.pointer += 1;
        console.log("[2. GRADE] Window complete! Advancing from " + oldPointer + " to " + this.pointer);

        // Don't auto-satisfy - player must explicitly play each onset
        // (Repeated chords will be handled by the player re-pressing the same keys)

        safety++;
      }

      if (this.pointer >= this.windowGroups.length) {
        this.finished = true;
        console.log("[2. GRADE] Exercise complete!");
      }
    },

    // Primary grading entrypoint used by ExerciseContext
    grade: function (definition, inputChords) {
      var graded = {
        result: PARTIAL,
        score: 1, // PARTIAL
        problems: [],
        activeIndex: Math.min(this.pointer, Math.max(0, this.windowGroups.length - 1)),
      };

      if (this._lastIncorrect) {
        graded.result = INCORRECT;
        graded.score = 2;
        this._lastIncorrect = false; // consume one-shot
        return graded;
      }

      if (this.finished) {
        graded.result = CORRECT;
        graded.score = 0;
        graded.activeIndex = this.windowGroups.length; // past-the-end
      }

      return graded;
    },
  });

  return ChoraleGrader;
});
