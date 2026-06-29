import $ from "jquery";
import _ from "lodash";
import Analyze from "app/utils/analyze";
import KeySignature from "app/models/key_signature";
import ScoreTimeline from "app/components/music/score_timeline";

/**
   * Dev-only script that loads a few corpus chorales and prints per-onset
   * roman numerals and figured bass (full/no8/abbrev) into #analysis-output.
   */

  function mapMetaKeyToModelKey(metaKey) {
    if (!metaKey || typeof metaKey !== "string") return null;
    var mk = metaKey.trim();
    var isMinor = /m$/i.test(mk);
    var root = isMinor ? mk.slice(0, -1) : mk;
    var letter = root.charAt(0).toUpperCase();
    var accidental = root.length > 1 ? root.slice(1) : ""; // '#', 'b', '##', 'bb'
    var suffix = accidental === "" ? "_" : accidental;
    return (isMinor ? "i" : "j") + letter + suffix; // e.g., jF_
  }

  function groupByOnset(timeline) {
    var groups = {};
    timeline.forEach(function (ev) {
      groups[ev.onset] = groups[ev.onset] || [];
      groups[ev.onset].push(ev);
    });
    var onsets = Object.keys(groups)
      .map(function (k) { return parseInt(k, 10); })
      .sort(function (a, b) { return a - b; });
    return onsets.map(function (on) { return { onset: on, events: groups[on] }; });
  }

  function toMidiStack(events) {
    // Sort so bass is first (lowest midi)
    return _.uniq(events.map(function (e) { return e.midi; }).sort(function (a, b) { return a - b; }));
  }

  function analyzeChorale(doc, opts) {
    opts = opts || {};
    var meta = (doc && doc.score && doc.score.meta) || {};
    var keyCode = mapMetaKeyToModelKey(meta.key) || "jC_";
    var ks = new KeySignature(keyCode);
    var analyzer = new Analyze(ks);

    var timeline = ScoreTimeline.buildTimeline(doc.score, { maxMeasures: opts.maxMeasures || 8 });
    var windows = groupByOnset(timeline);

    var lines = [];
    lines.push("=== Chorale: " + (doc.source && doc.source.workId || "(unknown)") + " | Key: " + (meta.key || "?") + " ===");
    windows.forEach(function (w, idx) {
      var midis = toMidiStack(w.events);
      var meas = _.min(w.events.map(function (e) { return e.measureIndex + 1; }));
      var full = analyzer.full_thoroughbass_figure(midis) || "";
      var no8 = analyzer.full_thoroughbass_figure_minus_octave(midis) || "";
      var abbr = analyzer.abbrev_thoroughbass_figure(midis) || "";
      var roman = "";
      if (typeof analyzer.to_chord === "function") {
        var rn = analyzer.to_chord(midis, "roman only");
        roman = rn && rn.label ? rn.label : "";
      }
      lines.push(
        [
          "m" + ("" + meas).padStart(3, " "),
          "on:" + ("" + w.onset).padStart(5, " "),
          "midi:[" + midis.join(",") + "]",
          "RN:" + roman,
          "FB:{full:" + full + ", no8:" + no8 + ", abbr:" + abbr + "}"
        ].join("  ")
      );
    });
    lines.push("");
    return lines.join("\n");
  }

  function loadJSON(url) {
    return $.getJSON(url);
  }

  function renderOutput(text) {
    var $out = $("#analysis-output");
    $out.append(document.createTextNode(text));
    $out.append("\n");
  }

  function run() {
    var files = [
      "/ajax/dev/corpus/bach/bwv1.6.json",
      "/ajax/dev/corpus/bach/bwv10.7.json",
      "/ajax/dev/corpus/bach/bwv101.7.json",
    ];

    var chain = Promise.resolve();
    files.forEach(function (u) {
      chain = chain.then(function () {
        return loadJSON(u).then(function (doc) {
          var txt = analyzeChorale(doc, { maxMeasures: 8 });
          renderOutput(txt);
        });
      });
    });
    chain.catch(function (e) {
      renderOutput("[error] " + e);
      // eslint-disable-next-line no-console
      console.error(e);
    });
  }

export default {
  ready: run
};
