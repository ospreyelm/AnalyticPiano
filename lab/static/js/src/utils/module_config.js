export function getModuleConfig(moduleId) {
  if (window.appConfig && window.appConfig.config && window.appConfig.config[moduleId]) {
    return window.appConfig.config[moduleId];
  }
  try {
    if (window.requirejs && window.requirejs.s && window.requirejs.s.contexts && window.requirejs.s.contexts._) {
      return window.requirejs.s.contexts._.config.config[moduleId] || {};
    }
  } catch (e) {}
  return {};
}
