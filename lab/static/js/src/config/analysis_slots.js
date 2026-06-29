

var TYPES = [
    { id: "roman_numerals",     label: "Roman numerals",       allowedZones: ["below"], anchor: "slice" },
    { id: "roman_numerals_exp", label: "Roman numerals (exp)", allowedZones: ["below"], anchor: "slice" },
    { id: "thoroughbass",       label: "Figured bass",         allowedZones: ["below"], anchor: "slice" },
    { id: "scale_degrees",      label: "Scale degrees",        allowedZones: ["above"], anchor: "note" },
    { id: "solfege",            label: "Solfège",              allowedZones: ["above"], anchor: "note" },
    { id: "note_names",         label: "Note names",           allowedZones: ["above"], anchor: "note" },
  ];
  var BY_ID = {}; TYPES.forEach(function (t) { BY_ID[t.id] = t; });

  var BELOW_MODES = ["roman_numerals_exp", "roman_numerals", "thoroughbass"];
  var ABOVE_MODES = ["scale_degrees", "solfege", "note_names"];

  function descriptor(id) { return BY_ID[id] || null; }
  function allowedZones(id) { var d = BY_ID[id]; return d ? d.allowedZones.slice() : []; }
  function canPlace(id, zone) { return allowedZones(id).indexOf(zone) >= 0; }
  function typesForZone(zone) {
    return TYPES.filter(function (t) { return t.allowedZones.indexOf(zone) >= 0; })
      .map(function (t) { return t.id; });
  }

  function normalizeSlots(cfg) {
    cfg = cfg || {};
    if (Object.prototype.hasOwnProperty.call(cfg, "above") ||
        Object.prototype.hasOwnProperty.call(cfg, "below")) {
      return { above: cfg.above || null, below: cfg.below || null };
    }
    var mode = cfg.mode || {};
    var below = null, above = null, i;
    for (i = 0; i < BELOW_MODES.length; i++) { if (mode[BELOW_MODES[i]]) { below = BELOW_MODES[i]; break; } }
    for (i = 0; i < ABOVE_MODES.length; i++) { if (mode[ABOVE_MODES[i]]) { above = ABOVE_MODES[i]; break; } }
    return { above: above, below: below };
  }

export default {
  TYPES: TYPES,
    descriptor: descriptor,
    allowedZones: allowedZones,
    canPlace: canPlace,
    typesForZone: typesForZone,
    normalizeSlots: normalizeSlots,
};
