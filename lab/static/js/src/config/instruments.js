import instrumentMap from "app/config/instruments_map";



export default {
  // defines a list of instrument numbers that are enabled
    enabled: [0, 6, 16, 25, 46, 52],

    // defines the available MIDI instruments
    // maps a MIDI instrument number to it's associated information
    instrumentMap: instrumentMap,
};
