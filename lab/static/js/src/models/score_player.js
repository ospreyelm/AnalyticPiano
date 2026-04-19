/* global define: false */
define(["lodash", "microevent", "Tone"], function (_, MicroEvent, Tone) {
  "use strict";

  var ScorePlayer = function (midiDevice) {
    this._midiDevice = midiDevice;
    this._bpm = 100;
    this._playing = false;
  };

  MicroEvent.mixin(ScorePlayer);

  function groupByOnset(timeline) {
    var map = {};
    var order = [];
    for (var i = 0; i < timeline.length; i++) {
      var ev = timeline[i];
      var key = ev.onset;
      if (!map[key]) { map[key] = []; order.push(key); }
      map[key].push(ev);
    }
    order.sort(function (a, b) { return a - b; });
    return order.map(function (onset) { return { onset: onset, events: map[onset] }; });
  }

  function ticksToSeconds(ticks, bpm) {
    return (ticks / 1024) * (60 / bpm);
  }

  _.extend(ScorePlayer.prototype, {
    play: function (timeline, bpm) {
      if (!timeline || !timeline.length) return;
      var self = this;
      var device = this._midiDevice;
      bpm = bpm || this._bpm;
      this._bpm = bpm;

      Tone.start().then(function () {
        Tone.Transport.stop();
        Tone.Transport.cancel();
        Tone.Transport.position = 0;

        var windows = groupByOnset(timeline);
        if (!windows.length) return;

        // Schedule note attacks and releases
        windows.forEach(function (win) {
          var attackTime = ticksToSeconds(win.onset, bpm);
          win.events.forEach(function (ev) {
            var releaseTime = ticksToSeconds(win.onset + ev.duration, bpm);
            Tone.Transport.schedule(function () {
              device.playNote(ev.midi);
            }, attackTime);
            Tone.Transport.schedule(function () {
              device.releaseNote(ev.midi);
            }, releaseTime);
          });
        });

        // Schedule tick callbacks (one per window)
        windows.forEach(function (win, idx) {
          Tone.Transport.schedule(function () {
            self.trigger("tick", idx);
          }, ticksToSeconds(win.onset, bpm));
        });

        // Schedule stopped event after last note release
        var lastRelease = 0;
        windows.forEach(function (win) {
          win.events.forEach(function (ev) {
            var t = ticksToSeconds(win.onset + ev.duration, bpm);
            if (t > lastRelease) lastRelease = t;
          });
        });
        Tone.Transport.schedule(function () {
          self._playing = false;
          device.releaseAllNotes();
          self.trigger("stopped");
        }, lastRelease + 0.05);

        self._playing = true;
        Tone.Transport.start();
      });
    },

    stop: function () {
      Tone.Transport.stop();
      Tone.Transport.cancel();
      this._midiDevice.releaseAllNotes();
      this._playing = false;
      this.trigger("stopped");
    },

    isPlaying: function () {
      return this._playing;
    },

    setTempo: function (bpm) {
      this._bpm = bpm;
    },
  });

  return ScorePlayer;
});
