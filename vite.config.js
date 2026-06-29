import { defineConfig } from "vite";
import { resolve } from "path";

export default defineConfig({
  base: "/static/dist/",
  resolve: {
    alias: [
      { find: /^app\/config$/, replacement: resolve(__dirname, "lab/static/js/src/config.js") },
      { find: "app", replacement: resolve(__dirname, "lab/static/js/src") },
      { find: "microevent", replacement: resolve(__dirname, "lab/static/js/lib/microevent.js") },
      { find: "vexflow", replacement: resolve(__dirname, "lab/static/js/lib/vexflow.js") },
      { find: "tonal", replacement: resolve(__dirname, "lab/static/js/lib/tonal.min.js") },
      { find: "Tone", replacement: resolve(__dirname, "lab/static/js/lib/Tone.js") },
      { find: /^lodash$/, replacement: resolve(__dirname, "lab/static/js/lib/lodash.js") },
      { find: "jquery", replacement: resolve(__dirname, "lab/static/js/lib/jquery.js") },
      { find: "raphael", replacement: resolve(__dirname, "lab/static/js/lib/raphael.js") },
      { find: "canvas-confetti", replacement: resolve(__dirname, "lab/static/js/lib/canvas-confetti.js") },
      { find: "file-saver", replacement: resolve(__dirname, "lab/static/js/lib/file-saver.js") },
      { find: "jquery-ui", replacement: resolve(__dirname, "lab/static/js/lib/jquery-ui.js") }
    ]
  },
  build: {
    manifest: true,
    outDir: resolve(__dirname, "lab/static/dist"),
    rollupOptions: {
      input: {
        key_signature: resolve(__dirname, "lab/static/js/src/models/key_signature.js"),
        chord: resolve(__dirname, "lab/static/js/src/models/chord.js"),
        key: resolve(__dirname, "lab/static/js/src/models/key_context_logic.js"),
        exercise_grader: resolve(__dirname, "lab/static/js/src/models/exercise_grader.js"),
        chorale_grader: resolve(__dirname, "lab/static/js/src/models/chorale_grader.js"),
        identification_grader: resolve(__dirname, "lab/static/js/src/models/identification_grader.js"),
        voice_leading: resolve(__dirname, "lab/static/js/src/models/voice_leading_logic.js"),
        exercise_definition: resolve(__dirname, "lab/static/js/src/models/exercise_definition.js"),
        exercise_definition_logic: resolve(__dirname, "lab/static/js/src/models/exercise_definition_logic.js"),
        exercise_definition_label_logic: resolve(__dirname, "lab/static/js/src/models/exercise_definition_label_logic.js"),
        exercise_chord: resolve(__dirname, "lab/static/js/src/models/exercise_chord.js"),
        exercise_chord_bank: resolve(__dirname, "lab/static/js/src/models/exercise_chord_bank.js"),
        midi_device: resolve(__dirname, "lab/static/js/src/models/midi_device.js"),
        metronome: resolve(__dirname, "lab/static/js/src/models/metronome.js"),
        score_player: resolve(__dirname, "lab/static/js/src/models/score_player.js"),
        barline_player: resolve(__dirname, "lab/static/js/src/barline_player_logic.js"),
        instruments: resolve(__dirname, "lab/static/js/src/config/instruments.js"),
        instruments_map: resolve(__dirname, "lab/static/js/src/config/instruments_map.js"),
        exercise_context: resolve(__dirname, "lab/static/js/src/models/exercise_context.js"),
        vexflow_adapter: resolve(__dirname, "lab/static/js/src/components/music/rendering/vexflow_adapter.js"),
        click_note: resolve(__dirname, "lab/static/js/src/components/input/click_note.js"),
        piano: resolve(__dirname, "lab/static/js/src/components/piano.js"),
        main: resolve(__dirname, "lab/static/js/src/main.js")
      }
    }
  },
  server: {
    host: "localhost",
    port: 5173,
    strictPort: true,
    headers: {
      "Access-Control-Allow-Origin": "*"
    }
  }
});
