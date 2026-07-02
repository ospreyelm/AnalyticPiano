import $ from "jquery";
import PlayApp from "app/components/app/play";
import ExerciseApp from "app/components/app/exercise";
import ManageApp from "app/components/app/manage";
import DebugAnalysisApp from "app/components/app/debug_analysis";

// Read app_module from the template-injected config payload, otherwise default to exercise
let appModule = null;
try {
  appModule = window.appConfig.config['app/main'].app_module;
} catch (e) {
  appModule = window.app_module || "app/components/app/exercise";
}

const appModules = {
  "app/components/app/play": PlayApp,
  "app/components/app/exercise": ExerciseApp,
  "app/components/app/manage": ManageApp,
  "app/components/app/debug_analysis": DebugAnalysisApp,
};

const app = appModules[appModule];
if (!app) {
  throw new Error("Unknown application module: " + appModule);
}

$(document).ready(app.ready);
