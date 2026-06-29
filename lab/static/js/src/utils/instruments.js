import _ from "lodash";
import Config from "app/config";

var ENABLED = Config.get("instruments.enabled");
  var INSTRUMENT_MAP = Config.get("instruments.instrumentMap");

  export default  {
    numberOf: function (name) {
      var num;
      for (num in INSTRUMENT_MAP) {
        if (
          INSTRUMENT_MAP.hasOwnProperty(num) &&
          INSTRUMENT_MAP[num].name.toLowerCase() === name.toLowerCase()
        ) {
          return parseInt(num, 10);
        }
      }
      return -1;
    },
    getEnabled: function () {
      return _.map(ENABLED, function (num, index) {
        return {
          num: num,
          name: INSTRUMENT_MAP[num].shortName || INSTRUMENT_MAP[num].name,
        };
      });
    },
  };
