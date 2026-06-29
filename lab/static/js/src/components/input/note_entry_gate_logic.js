

var TEXT_INPUT_TYPES = { text: true, search: true, email: true, url: true, tel: true, password: true, number: true };

  function shouldSuspendNoteEntry(tagName, inputType, isContentEditable) {
    if (isContentEditable) return true;
    if (!tagName) return false;
    var t = String(tagName).toUpperCase();
    if (t === "TEXTAREA") return true;
    if (t === "INPUT") {
      if (inputType == null) return true; // default <input> is text
      return TEXT_INPUT_TYPES[String(inputType).toLowerCase()] === true;
    }
    return false;
  }

export default {
  shouldSuspendNoteEntry: shouldSuspendNoteEntry
};
