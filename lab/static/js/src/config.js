import _ from "lodash";
import ConfigGeneral from "app/config/general";
import ConfigErrorText from "app/config/error_text";
import ConfigHighlight from "app/config/highlight";
import ConfigInstruments from "app/config/instruments";
import ConfigKeyboardShortcuts from "app/config/keyboard_shortcuts";
import ConfigAnalysis_hChords from "app/config/analysis/hChords";
import ConfigAnalysis_hIntervals from "app/config/analysis/hIntervals";
import ConfigAnalysis_iChords from "app/config/analysis/iChords";
import ConfigAnalysis_iDegrees from "app/config/analysis/iDegrees";
import ConfigAnalysis_ijIntervals from "app/config/analysis/ijIntervals";
import ConfigAnalysis_jChords from "app/config/analysis/jChords";
import ConfigAnalysis_jDegrees from "app/config/analysis/jDegrees";

/**
   * Defines an interface to retrieve config values.
   *
   * @namespace Config
   */
  var Config = {
    /**
     * Key separator for specifying nested values. Defaults to period.
     */
    keySeparator: ".",

    /** @private **/
    __config: {
      general: ConfigGeneral,
      errorText: ConfigErrorText,
      highlight: ConfigHighlight,
      instruments: ConfigInstruments,
      keyboardShortcuts: ConfigKeyboardShortcuts,
      analysis: {
        hChords: ConfigAnalysis_hChords,
        hIntervals: ConfigAnalysis_hIntervals,
        iChords: ConfigAnalysis_iChords,
        iDegrees: ConfigAnalysis_iDegrees,
        ijIntervals: ConfigAnalysis_ijIntervals,
        jChords: ConfigAnalysis_jChords,
        jDegrees: ConfigAnalysis_jDegrees,
      },
    },

    /**
     * Retrieves a config value.
     *
     * Use dot notation in the key string to retrieve nested config values.
     * For example, specifying key "x.y.z" will return the value of "z"
     * nested under "x" and "y."
     *
     * @param {string} key The dot-separated config value to retrieve.
     * @return The configuration value.
     * @throws {Error} Will throw an error if the key is invalid.
     */
    get: function (key) {
      if (typeof key !== "string") {
        throw new Error("Invalid parameter. Config key must be a string.");
      }

      var config = this.__config;
      var ks = this.keySeparator;
      var result, value;

      // lookup the key value
      result = _.reduce(
        key.split(ks),
        function (o, k) {
          o.path.push(k);
          if (o.value.hasOwnProperty(k)) {
            o.value = o.value[k];
          } else {
            throw new Error(
              "Invalid config key: [" +
                key +
                "] No such config value at: [" +
                o.path.join(ks) +
                "]"
            );
          }
          return o;
        },
        { value: config, path: [] }
      );

      // this copies the value to prevent or at least localize issues
      // that might occur if the config reference is modified by accident
      value = _.cloneDeep(result.value);

      return value;
    },
  };

export default Config;
