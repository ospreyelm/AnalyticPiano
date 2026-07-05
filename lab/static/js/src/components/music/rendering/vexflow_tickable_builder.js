import Vex from "vexflow";
import VexflowAdapterLogic from "app/components/music/rendering/vexflow_adapter_logic";
import HarmonizationRealizationLogic from "app/models/harmonization_realization_logic";

// barAlterations: mutable {step+octave -> alter} tracking within one measure.
  // Pass a shared object across all itemToTickable calls in the same measure+staff
  // so that G# earlier in the bar causes G♮ later to render an explicit natural.
  function itemToTickable(clef, item, octaveShift, idState, keySignatureAlterations, onset, measureIndex, showNotation, isAnalysisMatch, harmonizationOptions, barAlterations) {
    if (showNotation === undefined) showNotation = true;
    if (isAnalysisMatch === undefined) isAnalysisMatch = false;
    harmonizationOptions = harmonizationOptions || {};
    barAlterations = barAlterations || {};
    var hideForHarmonization = !!(harmonizationOptions.isHarmonization && harmonizationOptions.hideCurrentVoice);
    var voiceSlot = harmonizationOptions.voiceSlot || null;
    var voiceColors = harmonizationOptions.voiceColors || null;
    var voiceColor = (voiceSlot && voiceColors && voiceColors[voiceSlot]) || '#9aa0a6';
    if (item.kind === "rest") {
      var dur = VexflowAdapterLogic.durToVF(item.duration) + "r";
      var numDots = item.duration.dots || 0;
      var restKeyByClef = {
        treble: "b/4",
        bass: "d/3",
        alto: "c/4",
        tenor: "e/3",
      };
      var restKey = restKeyByClef[clef] || "b/4";
      // Shift rests away from the opposing voice to avoid collisions.
      if (clef === "treble" && voiceSlot === "S") restKey = "d/5";  // soprano: above staff
      if (clef === "treble" && voiceSlot === "A") restKey = "g/4";  // alto: below middle line
      if (clef === "bass"   && voiceSlot === "T") restKey = "f/3";  // tenor: above middle line
      // B slot uses restKeyByClef default (d/3) which is already low
      var rest = new Vex.Flow.StaveNote({
        clef: clef,
        keys: [restKey],
        duration: dur,
        dots: numDots
      });
      if (numDots > 0) Vex.Flow.Dot.buildAndAttach([rest], { all: true });

      // Tag with musical position
      rest._onset = onset;
      rest._measureIndex = measureIndex;
      rest._isRest = true;

      return rest;
    }
    if (item.kind === "note") {
      var alter = item.pitch.alter || 0;
      var acc = alter === 1 ? "#" : alter === -1 ? "b" : alter === 2 ? "##" : alter === -2 ? "bb" : "";
      var oshift = octaveShift || 0;
      var key = item.pitch.step.toLowerCase() + acc + "/" + (item.pitch.octave + oshift);
      var numDots = item.duration.dots || 0;
      var note = new Vex.Flow.StaveNote({ clef: clef, keys: [key], duration: VexflowAdapterLogic.durToVF(item.duration), dots: numDots });
      if (numDots > 0) Vex.Flow.Dot.buildAndAttach([note], { all: true });

      // Tag with musical position
      note._onset = onset;
      note._measureIndex = measureIndex;

      // Only show accidental if it contradicts the key signature or a prior note in the bar.
      var keyAlters = keySignatureAlterations || {};
      var step = item.pitch.step.toUpperCase();
      var keyAlter = keyAlters[step] || 0;
      var barKey = step + (item.pitch.octave + (octaveShift || 0));
      var effectiveAlter = barKey in barAlterations ? barAlterations[barKey] : keyAlter;

      if (alter !== effectiveAlter) {
        var accType = alter === 1 ? "#" : alter === -1 ? "b" : alter === 2 ? "##" : alter === -2 ? "bb" : "n";
        note.addModifier(new Vex.Flow.Accidental(accType), 0);
      }
      barAlterations[barKey] = alter;

      // Default: gray until played (will be set to black by matcher later)
      var played = idState && idState.playedNoteIds && idState.playedNoteIds.has(idState.nextId || 0);
      if (note.setStyle) {
        if (played) {
          note.setStyle({ fillStyle: '#000000', strokeStyle: '#000000' });
        } else if (!showNotation || isAnalysisMatch || hideForHarmonization) {
          note.setStyle({ fillStyle: "transparent", strokeStyle: "transparent" });
        } else {
          note.setStyle({ fillStyle: voiceColor, strokeStyle: voiceColor });
        }
      }
      if (idState) idState.nextId = (idState.nextId || 0) + 1;
      return note;
    }
    if (item.kind === "chord") {
      var oshift = octaveShift || 0;
      var keys = item.notes.map(function (n) {
        var alter = n.pitch.alter || 0;
        var acc = alter === 1 ? "#" : alter === -1 ? "b" : alter === 2 ? "##" : alter === -2 ? "bb" : "";
        return n.pitch.step.toLowerCase() + acc + "/" + (n.pitch.octave + oshift);
      });
      var numDots = item.duration.dots || 0;
      var chord = new Vex.Flow.StaveNote({ clef: clef, keys: keys, duration: VexflowAdapterLogic.durToVF(item.duration), dots: numDots });
      if (numDots > 0) Vex.Flow.Dot.buildAndAttach([chord], { all: true });

      // Only show accidentals that contradict the key signature or a prior note in the bar.
      var keyAlters = keySignatureAlterations || {};
      for (var i = 0; i < item.notes.length; i++) {
        var alter = item.notes[i].pitch.alter || 0;
        var step = item.notes[i].pitch.step.toUpperCase();
        var keyAlter = keyAlters[step] || 0;
        var barKey = step + (item.notes[i].pitch.octave + (octaveShift || 0));
        var effectiveAlter = barKey in barAlterations ? barAlterations[barKey] : keyAlter;

        if (alter !== effectiveAlter) {
          var accType = alter === 1 ? "#" : alter === -1 ? "b" : alter === 2 ? "##" : alter === -2 ? "bb" : "n";
          chord.addModifier(new Vex.Flow.Accidental(accType), i);
        }
        barAlterations[barKey] = alter;
      }

      // Tag with musical position
      chord._onset = onset;
      chord._measureIndex = measureIndex;

      // Default: gray until played (per notehead). resolveChordNoteStyles never
      // returns a black base style — per-key playedness can only ADD black to
      // specific noteheads via setKeyStyle below, never subtract it from the
      // others, so the base must stay at the unplayed color regardless of
      // whether some (but not all) notes in this chord have been played.
      if (chord.setStyle) {
        var resolved = VexflowAdapterLogic.resolveChordNoteStyles({
          keyCount: keys.length,
          baseId: idState ? (idState.nextId || 0) : 0,
          playedNoteIds: idState && idState.playedNoteIds,
          showNotation: showNotation,
          isAnalysisMatch: isAnalysisMatch,
          hideForHarmonization: hideForHarmonization,
          voiceColor: voiceColor,
        });
        chord.setStyle(resolved.baseStyle);
        for (var pk = 0; pk < resolved.playedKeyIndices.length; pk++) {
          if (chord.setKeyStyle) {
            chord.setKeyStyle(resolved.playedKeyIndices[pk], { fillStyle: '#000000', strokeStyle: '#000000' });
          }
        }
        // setKeyStyle only recolors individual noteheads — the shared stem
        // still draws in the transparent base style set above, so a played
        // chord shows black noteheads with an invisible stem. Reveal the
        // stem as soon as any key in the chord has been played.
        if (resolved.playedKeyIndices.length > 0 && chord.setStemStyle) {
          chord.setStemStyle({ fillStyle: '#000000', strokeStyle: '#000000' });
        }
      }
      if (idState) {
        idState.nextId = (idState.nextId || 0) + keys.length;
      }
      return chord;
    }
    return null;
  }

  function buildVoice(time, tickables) {
    var voice = new Vex.Flow.Voice(time);
    // Allow incomplete voices (for pickup measures / anacrusis)
    voice.setMode(Vex.Flow.Voice.Mode.SOFT);
    voice.addTickables(tickables);
    return voice;
  }

  function buildHarmonizationOverlayVoice(entriesInMeasure, measureTotalTicks, voiceTime, keySigAlters, colorOverride) {
    if (!entriesInMeasure || !entriesInMeasure.length || !HarmonizationRealizationLogic) return null;
    var sorted = entriesInMeasure.slice().sort(function (a, b) { return a.onset - b.onset; });
    var tickables = [];
    var cursor = 0;

    function makeTransparentRest(chunk) {
      var rest = new Vex.Flow.StaveNote({
        clef: "treble",
        keys: ["b/4"],
        duration: chunk.type + "r",
        dots: chunk.dots
      });
      if (chunk.dots > 0) Vex.Flow.Dot.buildAndAttach([rest], { all: true });
      if (rest.setStyle) rest.setStyle({ fillStyle: "transparent", strokeStyle: "transparent" });
      rest._isHarmonizationOverlay = true;
      rest._isOverlayRest = true;
      return rest;
    }

    function emitTransparentRests(ticks) {
      if (ticks <= 0) return true;
      var chunks = HarmonizationRealizationLogic.ticksToDurationChunks(ticks);
      if (!chunks) return false;
      for (var c = 0; c < chunks.length; c += 1) {
        tickables.push(makeTransparentRest(chunks[c]));
      }
      return true;
    }

    for (var i = 0; i < sorted.length; i += 1) {
      var entry = sorted[i];
      if (entry.onset < cursor) return null;
      if (!emitTransparentRests(entry.onset - cursor)) return null;

      // Overlay noteheads (pending/rejected click previews) use a fixed
      // placeholder duration that isn't real rhythm — clamp it to the room
      // left in the measure so a chord on the last beat still renders
      // instead of silently dropping the whole overlay voice below.
      var availableTicks = measureTotalTicks - entry.onset;
      var effectiveDuration = Math.min(entry.durationTicks, availableTicks);
      if (effectiveDuration <= 0) return null;

      var chunks = HarmonizationRealizationLogic.ticksToDurationChunks(effectiveDuration);
      if (!chunks || !chunks.length) return null;
      var headChunk = chunks[0];

      var defaultSpellings = [
        { step: "c", alter: 0 }, { step: "c", alter: 1 }, { step: "d", alter: 0 },
        { step: "e", alter: -1 }, { step: "e", alter: 0 }, { step: "f", alter: 0 },
        { step: "f", alter: 1 }, { step: "g", alter: 0 }, { step: "g", alter: 1 },
        { step: "a", alter: 0 }, { step: "b", alter: -1 }, { step: "b", alter: 0 }
      ];
      function midiToDefaultSpelling(m) {
        var pc = m % 12;
        var octave = Math.floor(m / 12) - 1;
        var info = defaultSpellings[pc];
        return { step: info.step, alter: info.alter, octave: octave };
      }

      var resolvedSpellings = entry.midiNotes.map(function (m, ki) {
        if (entry.spellings && entry.spellings[ki]) {
          return entry.spellings[ki];
        }
        return midiToDefaultSpelling(m);
      });

      var keys = resolvedSpellings.map(function (sp) {
        var acc = sp.alter === 1 ? "#"
                : sp.alter === -1 ? "b"
                : sp.alter === 2 ? "##"
                : sp.alter === -2 ? "bb"
                : "";
        return sp.step.toLowerCase() + acc + "/" + sp.octave;
      });

      var note = new Vex.Flow.StaveNote({
        clef: "treble",
        keys: keys,
        duration: headChunk.type,
        dots: headChunk.dots,
        auto_stem: false
      });
      if (headChunk.dots > 0) Vex.Flow.Dot.buildAndAttach([note], { all: true });
      note.setStemDirection(1);

      for (var ki2 = 0; ki2 < resolvedSpellings.length; ki2 += 1) {
        var sp2 = resolvedSpellings[ki2];
        var step2 = sp2.step.toUpperCase();
        var keyAlter = (keySigAlters && keySigAlters[step2]) || 0;
        if (sp2.alter !== keyAlter) {
          var accType = sp2.alter === 1 ? "#"
                      : sp2.alter === -1 ? "b"
                      : sp2.alter === 2 ? "##"
                      : sp2.alter === -2 ? "bb"
                      : "n";
          note.addModifier(new Vex.Flow.Accidental(accType), ki2);
        }
      }
      var overlayColor = colorOverride || "#000000";
      if (note.setStyle) note.setStyle({ fillStyle: overlayColor, strokeStyle: overlayColor });
      note._isHarmonizationOverlay = true;
      tickables.push(note);
      cursor = entry.onset + headChunk.ticks;

      for (var c2 = 1; c2 < chunks.length; c2 += 1) {
        tickables.push(makeTransparentRest(chunks[c2]));
        cursor += chunks[c2].ticks;
      }
    }

    if (cursor > measureTotalTicks) return null;
    if (!emitTransparentRests(measureTotalTicks - cursor)) return null;
    var voice = buildVoice(voiceTime, tickables);
    // Beam overlay noteheads per beat — mirrors the per-beat grouping used by
    // staffVoices for outer voices. Transparent rests are excluded so beams
    // span only adjacent noteheads within a beat.
    var notesOnly = tickables.filter(function (t) { return !t._isOverlayRest; });
    try {
      voice.beams = Vex.Flow.Beam.generateBeams(notesOnly, {
        beam_rests: false,
        stem_direction: 1,
      });
    } catch (e) {
      voice.beams = [];
    }
    return voice;
  }

export default {
  itemToTickable: itemToTickable,
    buildVoice: buildVoice,
    buildHarmonizationOverlayVoice: buildHarmonizationOverlayVoice,
};
