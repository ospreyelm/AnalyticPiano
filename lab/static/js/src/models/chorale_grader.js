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
      this._advanceTimer = null; // debounce timer for window advance

      // Track per-window details
      this.windowStats = [];      // Array of {status, correct, incorrect, completedAt}
      this.incorrectNotes = {};   // Map: windowIndex -> [midi numbers that were wrong]
    },

    initFromDefinition: function (definition) {
      this.reset();
      var score = definition.getScore ? definition.getScore() : null;
      if (!score) return this;

      console.log("[INIT] Score has " + (score.measures ? score.measures.length : 0) + " measures");

      this.timeline = ScoreTimeline.buildTimeline(score);
      var g = groupByOnset(this.timeline);
      // Sort groups by onset so the merge loop sees them in chronological order.
      // The timeline is in insertion order (voice-by-voice), so rawGroups is NOT
      // onset-ordered. Without sorting, the merge threshold check produces false
      // positives when onset differences are negative (later group followed by
      // earlier one), merging temporally distant notes into the same window.
      var tl = this.timeline;
      var rawGroups = g.groups.slice().sort(function(a, b) {
        return tl[a[0]].onset - tl[b[0]].onset;
      });

      this.windowGroups = [];
      var mergedGroup = [];
      var lastOnset = null;

      for (var w = 0; w < rawGroups.length; w++) {
        var groupIndices = rawGroups[w];
        var onset = this.timeline[groupIndices[0]].onset;

        // If this is the first group or onset is nearly identical to last, merge
        if (lastOnset === null || (onset - lastOnset <= 0.1)) {
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

      // Initialize window stats tracking
      this.windowStats = [];
      for (var w = 0; w < this.windowGroups.length; w++) {
        this.windowStats.push({
          status: 'not_started',
          correct: [],
          incorrect: [],
          completedAt: null
        });
      }

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

    getMeasureIndexForWindow: function (windowIdx) {
      if (!this.timeline.length || !this.windowGroups.length) return 0;
      var idxs = this.windowGroups[windowIdx];
      if (!idxs || !idxs.length) return 0;
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
      var heldNotes = this._getHeldNotesAtOnset(windowOnset, idxs);
      var allExpected = windowMidis.concat(heldNotes.map(function(ev) { return ev.midi; }));
      console.log("[2. GRADE] Current window onset=" + windowOnset +
                  ", new attacks:", windowMidis,
                  ", held notes:", heldNotes.map(function(e) {
                    return "midi=" + e.midi + " (onset=" + e.onset + ", dur=" + e.duration + ")";
                  }),
                  ", all expected:", allExpected);

      // Attempt to match all unplayed events in window with this MIDI pitch.
      // Multiple voices may share the same pitch — mark all of them played.
      var matched = false;
      for (var i = 0; i < idxs.length; i++) {
        var ev = tl[idxs[i]];
        if (!this.playedNoteIds.has(ev.id) && this._matchPitch(ev.midi, midi)) {
          this.playedNoteIds.add(ev.id);
          matched = true;
          console.log("[2. GRADE] ✓ Matched note " + midi + " in current window (id=" + ev.id + ")");
        }
      }

      // Also check held notes
      for (var j = 0; j < heldNotes.length; j++) {
        if (!this.playedNoteIds.has(heldNotes[j].id) && this._matchPitch(heldNotes[j].midi, midi)) {
          this.playedNoteIds.add(heldNotes[j].id);
          matched = true;
          console.log("[2. GRADE] ✓ Matched held note " + midi + " (id=" + heldNotes[j].id + ")");
          break;
        }
      }


      // If not matched in current window, check if it belongs to the next window.
      // This handles overlapping chord playing: the student releases the current
      // chord while pressing the next one, so next-chord notes arrive before the
      // debounce fires and advances the pointer.
      // Do NOT add to playedNoteIds here — just suppress the wrong-note penalty.
      // The note will be matched properly once the pointer advances.
      if (!matched && this._advanceTimer && this.pointer + 1 < this.windowGroups.length) {
        var nextIdxs = this.windowGroups[this.pointer + 1];
        var nextOnset = tl[nextIdxs[0]].onset;
        var nextHeld = this._getHeldNotesAtOnset(nextOnset, nextIdxs);
        for (var ni = 0; ni < nextIdxs.length; ni++) {
          var nev = tl[nextIdxs[ni]];
          if (this._matchPitch(nev.midi, midi)) {
            matched = true;
            console.log("[2. GRADE] ✓ Note " + midi + " belongs to next window — suppressing penalty");
            break;
          }
        }
        if (!matched) {
          for (var nh = 0; nh < nextHeld.length; nh++) {
            if (this._matchPitch(nextHeld[nh].midi, midi)) {
              matched = true;
              console.log("[2. GRADE] ✓ Held note " + midi + " belongs to next window — suppressing penalty");
              break;
            }
          }
        }
      }

      if (!matched) {
        // Wrong note for this window
        this.mistakeMade = true;
        this._lastIncorrect = true; // one-shot INCORRECT

        // Track which note was incorrect and in which window
        if (!this.incorrectNotes[this.pointer]) {
          this.incorrectNotes[this.pointer] = [];
        }
        if (this.incorrectNotes[this.pointer].indexOf(midi) === -1) {
          this.incorrectNotes[this.pointer].push(midi);
        }

        console.log("[2. GRADE] ✗ Wrong note " + midi + " for current window");
      }

      // Debounce window advance so simultaneous chord notes don't race.
      // Without this, note 1 of a chord completes the window and notes 2-4
      // arrive as wrong notes in the next window.
      var self = this;
      if (this._advanceTimer) clearTimeout(this._advanceTimer);
      this._advanceTimer = setTimeout(function () {
        self._advanceTimer = null;
        var oldPointer = self.pointer;
        self._advanceIfWindowComplete();
        if (self.pointer !== oldPointer) {
          console.log("[3. VISUAL] Advanced window pointer from " + oldPointer + " to " + self.pointer);
        }
      }, 150);
    },

    _matchPitch: function(expectedMidi, playedMidi) {
      if (expectedMidi === playedMidi) return true;
      
      // If octave independent/flexible, match based on pitch class (midi % 12)
      if (this.settings.octaveIndependent || this.settings.octaveFlexible) {
        return (expectedMidi % 12) === (playedMidi % 12);
      }
      
      return false;
    },

    _getHeldNotesAtOnset: function(onset, currentIdxs) {
      var tl = this.timeline;
      var held = [];
      var voiceSeen = {}; // track which voice/staff combos we've seen

      // Build set of voice keys already covered by new attacks in the current window.
      // A held note from the same voice as a new attack is a split fragment — don't
      // require the student to play it separately.
      var attackVoices = {};
      if (currentIdxs) {
        for (var a = 0; a < currentIdxs.length; a++) {
          var ae = tl[currentIdxs[a]];
          attackVoices[ae.staff + "_" + ae.voiceIndex] = true;
        }
      }

      // Walk backwards through timeline to find most recent event per voice before this onset
      for (var i = tl.length - 1; i >= 0; i--) {
        var ev = tl[i];
        if (ev.onset >= onset) continue; // skip events at or after current onset

        var key = ev.staff + "_" + ev.voiceIndex;
        if (voiceSeen[key]) continue; // already found most recent for this voice

        // Skip if this voice already has a new attack in the current window
        if (attackVoices[key]) {
          voiceSeen[key] = true;
          continue;
        }

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
        var heldNotes = this._getHeldNotesAtOnset(onset, idxs);
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

        // Mark window as complete and track notes
        var windowIdx = this.pointer;
        this.windowStats[windowIdx].status = 'complete';
        this.windowStats[windowIdx].completedAt = Date.now();

        // Record correct notes (all notes in this window that were played)
        var correctMidis = [];
        for (var n = 0; n < idxs.length; n++) {
          if (this.playedNoteIds.has(tl[idxs[n]].id)) {
            correctMidis.push(tl[idxs[n]].midi);
          }
        }
        for (var h = 0; h < heldNotes.length; h++) {
          if (this.playedNoteIds.has(heldNotes[h].id)) {
            correctMidis.push(heldNotes[h].midi);
          }
        }
        this.windowStats[windowIdx].correct = correctMidis;

        // Record incorrect notes for this window
        this.windowStats[windowIdx].incorrect = this.incorrectNotes[windowIdx] || [];

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

    // Phase 5: Expose score via getScore()
    getScore: function () {
      var denominator = this.windowGroups.length;
      var numerator = 0;
      for (var i = 0; i < this.windowStats.length; i++) {
        var s = this.windowStats[i];
        if (s.status === 'complete' && s.incorrect.length === 0) numerator++;
      }
      return { numerator: numerator, denominator: denominator };
    },

    // Primary grading entrypoint used by ExerciseContext
    grade: function (definition, inputChords) {
      var graded = {
        result: PARTIAL,
        score: 1, // PARTIAL
        problems: [],
        activeIndex: Math.min(this.pointer, Math.max(0, this.windowGroups.length - 1)),
      };

      // Build problems array from windowStats
      for (var w = 0; w < this.windowGroups.length; w++) {
        var stats = this.windowStats[w];
        var problem = {
          windowIndex: w,
          status: stats.status,
          score: stats.incorrect.length > 0 ? 2 : (stats.status === 'complete' ? 0 : 1),
          count: {
            correct: stats.correct,
            incorrect: stats.incorrect
          },
          note: {},     // Map each MIDI to correctness
          notes: stats.correct.concat(stats.incorrect)
        };

        // Build note map
        for (var c = 0; c < stats.correct.length; c++) {
          problem.note[stats.correct[c]] = 'correct';
        }
        for (var i = 0; i < stats.incorrect.length; i++) {
          problem.note[stats.incorrect[i]] = 'incorrect';
        }

        graded.problems.push(problem);
      }

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

        // Completion diagnostic summary
        var tl = this.timeline;
        var correctCount = 0;
        var failedWindows = [];
        for (var w = 0; w < this.windowStats.length; w++) {
          var s = this.windowStats[w];
          if (s.status === 'complete' && s.incorrect.length === 0) {
            correctCount++;
          } else if (s.incorrect.length > 0) {
            var expectedMidis = this.windowGroups[w].map(function(idx) { return tl[idx].midi; });
            failedWindows.push({
              window: w,
              incorrect: s.incorrect,
              expected: expectedMidis,
              isReattack: s.incorrect.every(function(m) { return expectedMidis.indexOf(m) !== -1; }),
            });
          }
        }
        var total = this.windowGroups.length;
        console.log('[SCORE] Completed: ' + correctCount + '/' + total + ' windows correct (' + Math.round(correctCount / total * 100) + '%)');
        if (failedWindows.length === 0) {
          console.log('[SCORE] No incorrect windows — perfect score');
        } else {
          failedWindows.forEach(function(fw) {
            var tag = fw.isReattack ? 'RE-ATTACK' : 'WRONG NOTE';
            console.log('[SCORE] Window ' + fw.window + ' FAILED [' + tag + '] — incorrect: [' + fw.incorrect.join(',') + '] | expected: [' + fw.expected.join(',') + ']');
          });
        }
      }

      return graded;
    },
  });

  return ChoraleGrader;
});
