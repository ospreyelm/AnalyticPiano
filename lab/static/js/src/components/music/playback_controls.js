import $ from "jquery";

var STORAGE_KEY = "harmonylab.playback.tempo";
  var DEFAULT_TEMPO = 100;

  function getSavedTempo() {
    try {
      var v = sessionStorage.getItem(STORAGE_KEY);
      if (v !== null) {
        var n = parseInt(v, 10);
        if (n >= 60 && n <= 160) return n;
      }
    } catch (e) {}
    return DEFAULT_TEMPO;
  }

  function saveTempo(bpm) {
    try { sessionStorage.setItem(STORAGE_KEY, String(bpm)); } catch (e) {}
  }

  function renderPlaybackControls(container, scorePlayer, getTimeline) {
    var $container = $(container);
    var $existing = $container.find("#playback-controls");

    if ($existing.length) {
      $existing.data("scorePlayer", scorePlayer);
      $existing.data("getTimeline", getTimeline);
      return;
    }

    var tempo = getSavedTempo();

    var html = [
      '<span id="playback-controls" style="display:inline-flex;align-items:center;gap:6px;margin-left:10px;">',
      '  <span style="border-left:1px solid #aaa;height:18px;margin-right:4px;"></span>',
      '  <button id="playback-play-btn" style="font-size:13px;padding:2px 8px;">&#9654; Play</button>',
      '  <input id="playback-tempo-slider" type="range" min="60" max="160" value="' + tempo + '" style="width:80px;">',
      '  <span id="playback-tempo-label" style="font-size:12px;min-width:50px;">' + tempo + ' bpm</span>',
      '</span>',
    ].join('');

    $container.append(html);

    var $ctrl = $container.find("#playback-controls");
    $ctrl.data("scorePlayer", scorePlayer);
    $ctrl.data("getTimeline", getTimeline);

    var $btn = $container.find("#playback-play-btn");
    var $slider = $container.find("#playback-tempo-slider");
    var $label = $container.find("#playback-tempo-label");

    function setButtonPlaying(playing) {
      $btn.html(playing ? "&#9632; Stop" : "&#9654; Play");
    }

    $btn.on("click", function () {
      var sp = $ctrl.data("scorePlayer");
      var gt = $ctrl.data("getTimeline");
      if (sp.isPlaying()) {
        sp.stop();
      } else {
        var tl = gt();
        if (!tl || !tl.length) return;
        var bpm = parseInt($slider.val(), 10);
        sp.play(tl, bpm);
        setButtonPlaying(true);
      }
    });

    $slider.on("input", function () {
      var bpm = parseInt($(this).val(), 10);
      $label.text(bpm + " bpm");
      saveTempo(bpm);
      var sp = $ctrl.data("scorePlayer");
      if (sp) sp.setTempo(bpm);
    });

    scorePlayer.bind("stopped", function () {
      setButtonPlaying(false);
    });
  }

export default renderPlaybackControls;
