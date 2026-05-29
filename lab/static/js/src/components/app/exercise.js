define([
  "module",
  "lodash",
  "jquery",
  "app/components/component",
  "app/components/app",
  "app/components/events",
  "app/components/piano",
  "app/components/music",
  "app/components/music/exercise_sheet",
  "app/components/music/symbolic_question_sheet",
  "app/components/midi",
  "app/components/notifications",
  "app/components/feedback_service",
  "app/config/feedback_catalog",
  "app/components/input/shortcuts",
  "app/components/input/note_name",
  "app/components/input/click_note",
  "app/components/input/click_note_logic",
  "app/components/input/computer_keyboard_ux_logic",
  "app/components/ui/main_menu",
  "app/components/ui/music_controls",
  "app/models/key_signature",
  "app/models/midi_device",
  "app/models/exercise_chord_bank",
  "app/models/exercise_definition",
  "app/models/exercise_grader",
  "app/models/chorale_grader",
  "app/models/identification_grader",
  "app/models/exercise_context",
  "app/components/exercise_score_card",
], function (
  module,
  _,
  $,
  Component,
  AppComponent,
  EVENTS,
  PianoComponent,
  MusicComponent,
  ExerciseSheetComponent,
  SymbolicQuestionSheet,
  MidiComponent,
  NotificationsComponent,
  FeedbackService,
  FeedbackCatalog,
  KeyboardShortcutsComponent,
  NoteNameInputComponent,
  ClickNoteInputComponent,
  ClickNoteLogic,
  ComputerKeyboardUxLogic,
  MainMenuComponent,
  MusicControlsComponent,
  KeySignature,
  MidiDevice,
  ExerciseChordBank,
  ExerciseDefinition,
  ExerciseGrader,
  ChoraleGrader,
  IdentificationGrader,
  ExerciseContext,
  ExerciseScoreCard
) {
  /**
   * AppExerciseComponent class.
   *
   * Creates the sandbox environment for playing and experimenting
   * with chords and chord sequences. This is the basic mode of the
   * application for students to just play around and try things.
   *
   * @constructor
   */
  var AppExerciseComponent = function (settings) {
    AppComponent.call(this, settings);
  };

  AppExerciseComponent.prototype = new AppComponent();

  /**
   * Returns the models used by the app.
   */
  AppExerciseComponent.prototype.getModels = function () {
    var models = {};
    var definition =
      this.getExerciseDefinition(); /* EXERCISE DATA ENTERS HERE */

    // console.log("Exercise data at initiation of AppExerciseComponent", definition);

    models.midiDevice = new MidiDevice();
    models.exerciseDefinition = new ExerciseDefinition({
      definition: definition,
    });

    // Skip sparse chorale_identification exercises before any rendering occurs.
    // If first page (first 4 measures) has fewer than 4 visible problems, redirect now.
    // Skip sparse chorale_identification exercises before any rendering occurs.
    // NOTE: This check is disabled for UMTO/Unit 1 exercises as they may have 
    // fewer than 4 measures but sufficient problems.
    if (
      false && // DISABLED: causing loops in Unit 1
      models.exerciseDefinition.isChoraleIdentification &&
      models.exerciseDefinition.isChoraleIdentification() &&
      definition.nextExercise
    ) {
      var allProblems = models.exerciseDefinition.getProblems ? models.exerciseDefinition.getProblems() : [];
      var score = models.exerciseDefinition.getScore ? models.exerciseDefinition.getScore() : null;
      var totalMeasures = score && score.measures ? score.measures.length : 0;
      var endMeasure = Math.min(4, totalMeasures);
      var visibleOnFirstPage = allProblems.filter(function (p) {
        return !p.hidden && p.measureIndex >= 0 && p.measureIndex < endMeasure;
      }).length;
      if (visibleOnFirstPage < 4) {
        window.location.replace(definition.nextExercise);
        return models; // abort further setup
      }
    }

    models.inputChords = new ExerciseChordBank({
      staffDistribution: definition.staffDistribution,
    });
    // Choose grader depending on exercise type/mode
    var interactionMode = models.exerciseDefinition.getMode();
    if (
      interactionMode === "identification" ||
      (!interactionMode && 
        ((models.exerciseDefinition.isIdentification && models.exerciseDefinition.isIdentification()) ||
         (models.exerciseDefinition.isChoraleIdentification && models.exerciseDefinition.isChoraleIdentification())))
    ) {
      console.log("[ID] Selecting IdentificationGrader (mode: " + interactionMode + ")");
      models.exerciseGrader = new IdentificationGrader({});
      models.exerciseGrader.initFromDefinition(models.exerciseDefinition);
    } else if (
      interactionMode === "playback" || 
      interactionMode === "analysis_match" ||
      (!interactionMode && models.exerciseDefinition.isChorale && models.exerciseDefinition.isChorale())
    ) {
      console.log("[ID] Selecting ChoraleGrader (mode: " + interactionMode + ")");
      var gradingSettings = models.exerciseDefinition.getGrading();
      // Unit 1 Bridge: Make grading octave-agnostic for Note Identification
      if (models.exerciseDefinition.isUnit(1)) {
        gradingSettings.octaveIndependent = true;
      }
      models.exerciseGrader = new ChoraleGrader(gradingSettings);
      // Initialize from definition so it has the timeline ready
      models.exerciseGrader.initFromDefinition(models.exerciseDefinition);
    } else {
      models.exerciseGrader = new ExerciseGrader({
        keySignature: new KeySignature(
          models.exerciseDefinition.getKey(),
          models.exerciseDefinition.getKeySignature()
        ),
      });
    }
    var scoreCard = new ExerciseScoreCard();
    scoreCard.init(document.getElementById("staff-area") || document.body);
    models.scoreCard = scoreCard;

    models.exerciseContext = new ExerciseContext({
      inputChords: models.inputChords,
      grader: models.exerciseGrader,
      definition: models.exerciseDefinition,
      exercise: this,
      scoreCard: scoreCard,
    });

    if (models.exerciseContext._isIdentificationExercise && models.exerciseContext._isIdentificationExercise()) {
      if (definition.reviewMode && definition.reviewAnswers) {
        models.exerciseGrader.answers = _.clone(definition.reviewAnswers);
      } else if (definition.exerciseId) {
        models.exerciseContext.restoreIdentState(definition.exerciseId);
      }
    }

    models.keySignature = new KeySignature(
      models.exerciseDefinition.getKey(),
      models.exerciseDefinition.getKeySignature()
    );
    return models;
  };

  /**
   * Returns the exercise definition.
   */
  AppExerciseComponent.prototype.getExerciseDefinition = function () {
    var exercise_config = module.config(); /* EXERCISE DATA ENTERS HERE */
    if (!exercise_config) {
      throw new Error(
        "getExerciseDefinition(): missing exercise configuration data"
      );
    }
    return exercise_config; //$.extend(true, {}, exercise_config); // Return deep copy of the config
  };

  /**
   * Returns an array of functions that will create and initialize
   * each sub-component of the application.
   *
   * @return {array} of functions
   */
  AppExerciseComponent.prototype.getComponentMethods = function () {
    var definition = this.getExerciseDefinition();
    var disableComputerKeyboardInput = !!definition.disableComputerKeyboardInput;
    var isSymbolicMeterExercise = definition.type === "umto_symbolic_meter";
    var isKeySignatureExercise = definition.type === "umto_key_signature";
    // Analysis/identification exercises answer via mouse (? slots) or text input,
    // not MIDI/Click note entry — so the Live/Click source toggle and the
    // click-on-staff component do not apply. Gate on interaction MODE (type alone
    // misses e.g. analysis_match on a harmonization/chorale type), with the
    // type-based predicate as a fallback.
    var exerciseMode = definition.getMode ? definition.getMode() : null;
    var isAnalysisExercise =
      exerciseMode === "identification" ||
      exerciseMode === "chorale_identification" ||
      exerciseMode === "analysis_match" ||
      exerciseMode === "analysis" ||
      !!(definition.isIdentification && definition.isIdentification());
    var _ex = definition.exercise || {};
    var _umeta = (_ex.score && _ex.score.umto && _ex.score.umto.metadata) || {};
    console.log("[SOURCE-TOGGLE-GATE]",
      "id=", _ex.exerciseId || _ex.id,
      "type=", definition.type,
      "mode=", exerciseMode,
      "analysisType=", (definition.getAnalysisType && definition.getAnalysisType()),
      "umto.metadata.mode=", _umeta.mode,
      "umto.metadata.interaction_mode=", _umeta.interaction_mode,
      "isIdentification=", (definition.isIdentification && definition.isIdentification()),
      "isChoraleIdentification=", (definition.isChoraleIdentification && definition.isChoraleIdentification()),
      "isAnalysisExercise=", isAnalysisExercise,
      "| metadata keys=", Object.keys(_umeta), "| exercise:", _ex);
    var methods = [
      function () {
        var c = new FeedbackService({ exerciseContext: this.models.exerciseContext });
        c.init(this);
        this.models.feedback = c;
        if (this.models.exerciseContext) {
          this.models.exerciseContext.feedback = c;
          this.models.exerciseContext._feedbackCatalog = FeedbackCatalog;
        }
        this.addComponent(c);
      },
      function () {
        var c = new NotificationsComponent({ defaultHidden: false });
        c.init(this);
        c.renderTo("#notifications", "#notificationAlerts");
        this.addComponent(c);
      },
      function () {
        if (isSymbolicMeterExercise || isKeySignatureExercise) {
          return;
        }
        var c = new PianoComponent({
          toolbarConfig: { metronome: false },
          toolbarEnabled: false,
        });
        c.init(this);
        c.renderTo("#piano");
        this.addComponent(c);
      },
      function () {
        if (isSymbolicMeterExercise || isKeySignatureExercise) {
          return;
        }
        var c = new MidiComponent({
          chords: this.models.inputChords,
          midiDevice: this.models.midiDevice,
          feedback: this.models.feedback,
        });
        c.init(this);
        this.addComponent(c);
      },
      function () {
        if (disableComputerKeyboardInput || isSymbolicMeterExercise || isKeySignatureExercise) {
          return;
        }
        var c = new KeyboardShortcutsComponent({
          keySignature: this.models.keySignature,
        });
        c.init(this);
        this.addComponent(c);
      },
      function () {
        if (disableComputerKeyboardInput || isSymbolicMeterExercise || isKeySignatureExercise) {
          return;
        }
        var c = new NoteNameInputComponent({
          defaultMode: ComputerKeyboardUxLogic._getDefaultExerciseInputMode()
        });
        c.init(this);
        c.renderTo("#piano");
        this.addComponent(c);
      },
      function () {
        var c = new MainMenuComponent({
          headerEl: "#header",
          menuEl: "#mainmenu",
          menuSelector: ".js-btn-menu",
        });
        c.init(this);
        this.addComponent(c);
      },
      function () {
        if (isSymbolicMeterExercise || isKeySignatureExercise) {
          return;
        }
        var c = new MusicControlsComponent({
          headerEl: "#header",
          containerEl: "#mainmenu",
          keySignature: this.models.keySignature,
          midiDevice: this.models.midiDevice,
          exerciseContext: this.models.exerciseContext,
        });
        c.init(this);
        this.addComponent(c);
      },
      function () {
        var definition = this.models.exerciseContext.getDefinition();

        if (definition.isSymbolicMeterQuestion && definition.isSymbolicMeterQuestion()) {
          var symbolicSheet = new SymbolicQuestionSheet({
            exerciseContext: this.models.exerciseContext,
          });
          symbolicSheet.init(this);
          symbolicSheet.renderTo("#staffwrapper");
          this.addComponent(symbolicSheet);
          return;
        }

        if (definition.isKeySignatureExercise && definition.isKeySignatureExercise()) {
          var self = this;
          var toolbar = document.getElementById("staff-toolbar");
          if (toolbar) toolbar.style.display = "none";
          var wrapper = document.getElementById("staffwrapper");
          if (wrapper) {
            wrapper.style.display = "flex";
            wrapper.style.flexDirection = "column";
            wrapper.style.alignItems = "center";
            wrapper.style.paddingTop = "32px";
            wrapper.innerHTML =
              '<div class="key-sig-staff-container"></div>' +
              '<div class="key-sig-choices" style="margin-top:20px;display:flex;flex-wrap:wrap;gap:10px;justify-content:center;"></div>' +
              '<span class="key-sig-feedback" style="display:block;margin-top:10px;font-size:1em;min-height:1.4em;text-align:center"></span>';
          }
          require(["app/models/key_sig_exercise"], function (KeySigMod) {
            var exc = self.models.exerciseContext;
            var feedbackEl = document.querySelector(".key-sig-feedback");
            var choicesEl = document.querySelector(".key-sig-choices");

            var keySigEx = new KeySigMod.KeySigExercise(definition, {
              staffContainer: document.querySelector(".key-sig-staff-container"),
              choicesEl: choicesEl,
              onComplete: function (gradeData) {
                if (exc.sealed) return;
                // Patch the grader so submitExerciseReport reports the real score.
                if (gradeData && exc.grader) {
                  var n = gradeData.numerator != null ? gradeData.numerator : gradeData.denominator;
                  var d = gradeData.denominator || 0;
                  exc.grader.getScore = function () {
                    return { numerator: n, denominator: d };
                  };
                }
                exc.makeTimestamp();
                exc.done = true;
                if (!exc.timer) { exc.triggerTimer(); }
                exc.endTimer();
                exc.submitExerciseReport();
                exc.state = exc.constructor.STATE.CORRECT;
                exc.sealed = true;
                if (exc.exercise && typeof exc.exercise.trigger === "function") {
                  exc.exercise.trigger("change");
                }
                exc.trigger("graded");
                exc.triggerNextExercise();
                $(".playlist-nav-links").css("display", "inline-flex");
              },
              onAdvance: function () {
                if (feedbackEl) feedbackEl.textContent = "";
              },
              onWrong: function (msg) {
                if (feedbackEl) {
                  feedbackEl.textContent = msg || "Try again.";
                  feedbackEl.style.color = "#c00";
                }
              },
            });
            keySigEx.start();
          });
          return;
        }

        var exerciseSheet = new ExerciseSheetComponent({
          exerciseContext: this.models.exerciseContext,
          keySignature: this.models.keySignature,
          midiDevice: this.models.midiDevice,
        });
        this.models.exerciseSheet = exerciseSheet;
        var c = new MusicComponent({
          el: $("#staff-area"),
          sheet: exerciseSheet,
          analysisSettings: definition.getAnalysisSettings(),
          staffDistribution: definition.getStaffDistribution(),
          highlightSettings: definition.getHighlightSettings(),
        });
        c.init(this);
        var exercise_midi_nums =
          c.settings.sheet.exerciseContext.exerciseChords._items.map((item) =>
            item.getNoteNumbers()
          );
        c.render(exercise_midi_nums); // send midi nums from exercise chords ahead for the purposes of contextual Roman numeral analysis
        this.addComponent(c);
      },
      function () {
        if (disableComputerKeyboardInput || isSymbolicMeterExercise || isKeySignatureExercise || isAnalysisExercise) {
          return;
        }
        if (!this.models.exerciseSheet) {
          return;
        }
        var c = new ClickNoteInputComponent({
          sheet: this.models.exerciseSheet,
          exerciseContext: this.models.exerciseContext,
          keySignature: this.models.keySignature,
          midiDevice: this.models.midiDevice,
          feedback: this.models.feedback,
        });
        c.init(this);
        c.renderTo("#staff-area");
        this.addComponent(c);
      },
      function () {
        if (disableComputerKeyboardInput || isSymbolicMeterExercise || isKeySignatureExercise || isAnalysisExercise) {
          return;
        }
        if (!this.models.exerciseSheet) {
          return;
        }
        var SOURCE_MODE_KEY = "harmonylab.inputSourceMode";
        var self = this;
        var manualChoice = false;
        var $wrap = $('<div class="input-source-mode-toggle" aria-label="Input source"></div>');
        var $live = $('<button type="button" class="input-mode-btn" title="Use MIDI or computer keyboard input">MIDI</button>');
        var $click = $('<button type="button" class="input-mode-btn" title="Click notes onto the staff, then press Done">Click</button>');
        $wrap.append($live).append($click);
        var $next = $("#staff-toolbar .js-btn-nextexercise").first();
        if ($next.length) {
          $wrap.insertBefore($next);
        } else {
          $("#piano").prepend($wrap);
        }
        var $modeMsg = $('<div class="feedback-inline" role="status" aria-live="polite"></div>');
        $wrap.after($modeMsg);

        function readStoredMode() {
          try {
            return window.localStorage.getItem(SOURCE_MODE_KEY);
          } catch (e) {
            return null;
          }
        }

        function persistMode(mode) {
          try {
            window.localStorage.setItem(SOURCE_MODE_KEY, mode);
          } catch (e) {}
        }

        function syncButtons(mode) {
          $live
            .toggleClass("input-mode-btn-active", mode === "live")
            .toggleClass("input-mode-btn-inactive", mode !== "live");
          $click
            .toggleClass("input-mode-btn-active", mode === "click")
            .toggleClass("input-mode-btn-inactive", mode !== "click");
        }

        function applySourceMode(mode) {
          self.broadcast(EVENTS.BROADCAST.INPUT_SOURCE_MODE, mode);
          var sheet = self.models && self.models.exerciseSheet;
          if (sheet && sheet.setInputSourceMode) sheet.setInputSourceMode(mode);
          syncButtons(mode);
        }

        self._setInputSourceMode = function (mode) {
          manualChoice = true;
          persistMode(mode);
          if (self.models.feedback) {
            self.models.feedback.emit(
              mode === "click" ? "input.mode.changed_click" : "input.mode.changed_live",
              { inlineEl: $modeMsg }
            );
          }
          applySourceMode(mode);
        };

        $live.on("click", function (e) {
          e.preventDefault();
          self._setInputSourceMode("live");
        });
        $click.on("click", function (e) {
          e.preventDefault();
          self._setInputSourceMode("click");
        });

        applySourceMode(ClickNoteLogic.defaultSourceMode(0, readStoredMode()));
        self.subscribe(EVENTS.BROADCAST.MIDI_INPUTS_CHANGED, function (payload) {
          if (manualChoice || readStoredMode()) return;
          applySourceMode(
            ClickNoteLogic.defaultSourceMode((payload && payload.inputCount) || 0, null)
          );
        });
      },
    ];
    return methods;
  };

  /**
   * Initializes the application.
   * Intended to be called $(document).ready().
   *
   * @return undefined
   */
  AppExerciseComponent.ready = function () {
    app = new AppExerciseComponent();
    app.init();
    app.log("App ready");
  };

  return AppExerciseComponent;
});
