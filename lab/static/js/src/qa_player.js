(function () {
  "use strict";

  var MUSIC_FONT = '"Bravura Text","Finale Maestro Text","Petaluma Script","Noto Music",serif';
  var STORAGE_TTL_MS = 7 * 24 * 60 * 60 * 1000;

  function escapeHTML(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;");
  }

  function renderPromptHTML(prompt) {
    if (!prompt) {
      return "";
    }

    if (prompt.kind === "time_signature" && /^\d+\/\d+$/.test(prompt.text || "")) {
      var parts = prompt.text.split("/");
      return (
        '<span class="meter-ts" style="font-family:' + MUSIC_FONT + '">' +
        '<span class="meter-ts-top">' + parts[0] + "</span>" +
        '<span class="meter-ts-bottom">' + parts[1] + "</span>" +
        "</span>"
      );
    }

    return "<span>" + escapeHTML(prompt.text || "") + "</span>";
  }

  function questionStem(problem) {
    var subtype = problem && (problem.subtype || problem.promptSubtype);
    var STEMS = {
      ts_to_grouping: "What is the beat grouping?",
      ts_to_division_type: "Is this meter simple or compound?",
      ts_to_beat_value: "What is the beat level?",
      ts_to_division_value: "What is the division level?",
      ts_to_beat_count: "How many beats are in this bar?",
      ts_to_division_count: "How many divisions are in this bar?",
      ts_to_full_meter: "What type of meter is this?",
      meter_to_ts: "Which time signature represents this meter?"
    };

    if (subtype && STEMS[subtype]) {
      return STEMS[subtype];
    }

    if (problem && problem.prompt && problem.prompt.kind === "meter_label") {
      return "Which time signature matches this full meter label?";
    }

    return "Choose the correct answer.";
  }

  function shuffleArray(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  }

  function getCookie(name) {
    var value = "; " + document.cookie;
    var parts = value.split("; " + name + "=");
    if (parts.length === 2) {
      return parts.pop().split(";").shift();
    }
    return "";
  }

  function storageKey(exerciseId) {
    return "qa:" + exerciseId;
  }

  function loadSaved(exerciseId) {
    try {
      var raw = localStorage.getItem(storageKey(exerciseId));
      if (!raw) {
        return null;
      }

      var obj = JSON.parse(raw);
      if (Date.now() - (obj.savedAt || 0) > STORAGE_TTL_MS) {
        localStorage.removeItem(storageKey(exerciseId));
        return null;
      }
      return obj;
    } catch (e) {
      return null;
    }
  }

  function saveState(state) {
    try {
      localStorage.setItem(
        storageKey(state.exerciseId),
        JSON.stringify({
          answers: state.answers,
          revealed: state.revealed,
          page: state.page,
          submitted: state.submitted,
          savedAt: Date.now()
        })
      );
    } catch (e) {
      return;
    }
  }

  function clearSaved(exerciseId) {
    try {
      localStorage.removeItem(storageKey(exerciseId));
    } catch (e) {
      return;
    }
  }

  function saveResults(config, answers) {
    var problems = config.problems || [];
    var correctness = {};
    var correctAnswers = {};
    var correctCount = 0;
    var incorrectCount = 0;

    problems.forEach(function (problem, i) {
      var chosen = answers[i];
      var isCorrect = chosen === problem.answer;
      correctness[i] = isCorrect;
      correctAnswers[i] = problem.answer;
      if (isCorrect) {
        correctCount += 1;
      } else {
        incorrectCount += 1;
      }
    });

    var payload = {
      course_ID: config.courseId || null,
      playlist_ID: config.playlistName,
      exercise_num: config.exerciseNum,
      answers: answers,
      correctness: correctness,
      score: {
        correct: correctCount,
        incorrect: incorrectCount,
        unanswered: 0
      },
      correct_answers: correctAnswers,
      page_num: 0,
      is_page_submit: false,
      mode: config.inputMode || "flashcard",
      attempt_type: "practice"
    };

    fetch("/ajax/identification-answers/", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": getCookie("csrftoken")
      },
      body: "data=" + encodeURIComponent(JSON.stringify(payload))
    }).catch(function () {
      return;
    });
  }

  function makeInitialState(config) {
    var saved = loadSaved(config.exerciseId);
    var problems = saved ? (config.problems || []) : shuffleArray(config.problems || []);
    return {
      exerciseId: config.exerciseId,
      problems: problems,
      mode: config.inputMode === "quiz" ? "quiz" : "flashcard",
      answers: (saved && saved.answers) || {},
      revealed: (saved && saved.revealed) || {},
      page: (saved && saved.page) || 0,
      submitted: (saved && saved.submitted) || false,
      nextExerciseUrl: config.nextExercise || null
    };
  }

  function cloneState(state) {
    return {
      exerciseId: state.exerciseId,
      problems: state.problems,
      mode: state.mode,
      answers: Object.assign({}, state.answers),
      revealed: Object.assign({}, state.revealed),
      page: state.page,
      submitted: state.submitted,
      nextExerciseUrl: state.nextExerciseUrl
    };
  }

  function dispatch(state, action) {
    var s = cloneState(state);

    if (action.type === "SELECT_ANSWER") {
      if (s.mode === "flashcard") {
        if (s.revealed[action.index]) {
          return s;
        }
        s.answers[action.index] = action.answer;
        s.revealed[action.index] = true;
        saveState(s);
        return s;
      }

      if (!s.submitted) {
        s.answers[action.index] = action.answer;
        saveState(s);
      }
      return s;
    }

    if (action.type === "NEXT_PAGE") {
      if (s.mode === "flashcard") {
        s.page = Math.min(Math.max(action.page, 0), Math.max(s.problems.length - 1, 0));
        saveState(s);
      }
      return s;
    }

    if (action.type === "SUBMIT_QUIZ") {
      if (s.mode === "quiz" && !s.submitted) {
        s.submitted = true;
        s.revealed = {};
        s.problems.forEach(function (_, i) {
          s.revealed[i] = true;
        });
        saveState(s);
      }
      return s;
    }

    return s;
  }

  function buildFlashcardHTML(state) {
    var problems = state.problems;
    var page = Math.min(Math.max(state.page, 0), Math.max(problems.length - 1, 0));
    var problem = problems[page];

    if (!problem) {
      return '<p style="padding:24px">No problems found.</p>';
    }

    var chosen = state.answers[page];
    var isRevealed = !!state.revealed[page];
    var isCorrect = isRevealed && chosen === problem.answer;

    var choicesHTML = (problem.choices || []).map(function (choice) {
      var cls = "qa-choice";
      if (isRevealed && chosen === choice) {
        cls += isCorrect ? " correct" : " incorrect";
      }
      return (
        '<button type="button" class="' + cls + '"' +
        (isRevealed ? " disabled" : "") +
        ' data-choice="' + escapeHTML(choice) + '"' +
        ' data-index="' + page + '">' +
        escapeHTML(choice) +
        "</button>"
      );
    }).join("");

    var feedbackHTML = "";
    if (isRevealed) {
      if (isCorrect) {
        feedbackHTML = '<div class="qa-feedback qa-feedback-correct">Correct!</div>';
      } else {
        feedbackHTML =
          '<div class="qa-feedback qa-feedback-incorrect">Incorrect - correct answer: ' +
          escapeHTML(problem.answer) +
          "</div>" +
          '<button type="button" class="qa-next-btn" data-action="next" data-page="' +
          (page + 1) +
          '">Next</button>';
      }
    }

    return (
      '<div class="qa-progress">' +
      (page + 1) +
      " / " +
      problems.length +
      "</div>" +
      '<div class="qa-card">' +
      '<div class="qa-stem">' + escapeHTML(questionStem(problem)) + "</div>" +
      '<div class="qa-prompt">' + renderPromptHTML(problem.prompt) + "</div>" +
      '<div class="qa-choices">' + choicesHTML + "</div>" +
      feedbackHTML +
      "</div>"
    );
  }

  function buildQuizHTML(state) {
    var problems = state.problems;
    var allAnswered = problems.every(function (_, i) {
      return state.answers[i] !== undefined;
    });

    var cardsHTML = problems.map(function (problem, i) {
      var chosen = state.answers[i];
      var isRevealed = !!state.revealed[i];
      var isCorrect = isRevealed && chosen === problem.answer;

      var choicesHTML = (problem.choices || []).map(function (choice) {
        var cls = "qa-choice";
        if (!isRevealed && chosen === choice) {
          cls += " selected";
        }
        if (isRevealed && chosen === choice) {
          cls += isCorrect ? " correct" : " incorrect";
        }

        return (
          '<button type="button" class="' + cls + '"' +
          (isRevealed ? " disabled" : "") +
          ' data-choice="' + escapeHTML(choice) + '"' +
          ' data-index="' + i + '">' +
          escapeHTML(choice) +
          "</button>"
        );
      }).join("");

      var feedbackHTML = "";
      if (isRevealed) {
        feedbackHTML = isCorrect
          ? '<div class="qa-feedback qa-feedback-correct">Correct</div>'
          : '<div class="qa-feedback qa-feedback-incorrect">Incorrect - ' +
            escapeHTML(problem.answer) +
            "</div>";
      }

      return (
        '<div class="qa-card">' +
        '<div class="qa-stem">' + escapeHTML(questionStem(problem)) + "</div>" +
        '<div class="qa-prompt">' + renderPromptHTML(problem.prompt) + "</div>" +
        '<div class="qa-choices">' + choicesHTML + "</div>" +
        feedbackHTML +
        "</div>"
      );
    }).join("");

    if (state.submitted) {
      var correctCount = problems.filter(function (problem, i) {
        return state.answers[i] === problem.answer;
      }).length;

      return (
        '<div class="qa-complete-banner">Done - ' +
        correctCount +
        " / " +
        problems.length +
        " correct" +
        (state.nextExerciseUrl
          ? '<br><a class="qa-next-exercise-btn" href="' +
            escapeHTML(state.nextExerciseUrl) +
            '">Next Exercise</a>'
          : "") +
        "</div>" +
        cardsHTML
      );
    }

    return (
      cardsHTML +
      '<div class="qa-submit-bar">' +
      '<button type="button" class="qa-submit-btn" data-action="submit"' +
      (allAnswered ? "" : " disabled") +
      ">Submit</button>" +
      "</div>"
    );
  }

  function render(state) {
    var root = document.getElementById("qa-root");
    if (!root) {
      return;
    }

    root.innerHTML = state.mode === "quiz" ? buildQuizHTML(state) : buildFlashcardHTML(state);
  }

  function attachHandlers(app) {
    var root = document.getElementById("qa-root");
    if (!root) {
      return;
    }

    root.onclick = function (e) {
      var button = e.target.closest("button");
      if (!button) {
        return;
      }

      var action = button.dataset.action;
      var choice = button.dataset.choice;
      var indexStr = button.dataset.index;

      if (action === "submit") {
        app.state = dispatch(app.state, { type: "SUBMIT_QUIZ" });
        saveResults(app.config, app.state.answers);
        clearSaved(app.state.exerciseId);
        render(app.state);
        return;
      }

      if (action === "next") {
        var nextPage = parseInt(button.dataset.page, 10);
        if (isNaN(nextPage)) {
          return;
        }
        app.state = dispatch(app.state, { type: "NEXT_PAGE", page: nextPage });
        render(app.state);
        return;
      }

      if (choice === undefined || indexStr === undefined) {
        return;
      }

      var index = parseInt(indexStr, 10);
      if (isNaN(index)) {
        return;
      }

      app.state = dispatch(app.state, {
        type: "SELECT_ANSWER",
        index: index,
        answer: choice
      });
      render(app.state);

      if (app.state.mode !== "flashcard") {
        return;
      }

      var problem = app.state.problems[index];
      var isCorrect = problem && app.state.answers[index] === problem.answer;
      if (!isCorrect) {
        return;
      }

      var isLast = index >= app.state.problems.length - 1;
      if (isLast) {
        saveResults(app.config, app.state.answers);
        clearSaved(app.state.exerciseId);
        window.setTimeout(function () {
          if (app.state.nextExerciseUrl) {
            window.location.href = app.state.nextExerciseUrl;
          }
        }, 1000);
        return;
      }

      window.setTimeout(function () {
        app.state = dispatch(app.state, { type: "NEXT_PAGE", page: index + 1 });
        render(app.state);
      }, 800);
    };
  }

  document.addEventListener("DOMContentLoaded", function () {
    var config = window.__EXERCISE_CONFIG__;
    if (!config || config.type !== "umto_symbolic_meter") {
      return;
    }

    var app = {
      config: config,
      state: makeInitialState(config)
    };

    render(app.state);
    attachHandlers(app);
  });
})();
