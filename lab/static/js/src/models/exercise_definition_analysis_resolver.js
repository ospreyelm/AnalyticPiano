import LabelLogic from "app/models/exercise_definition_label_logic";

/**
 * Resolves the answer string for a given analysis type from the slice content.
 *
 * @param {string} analysisType
 * @param {object} content The slice content object
 * @return {string} The resolved answer
 */
export function resolveAnalysisAnswer(analysisType, content) {
  if (!content) {
    return "";
  }

  var answer = "";

  if (analysisType === "chord_quality" && content.chord_quality != null) {
    answer = content.chord_quality;
  } else if (analysisType === "figured_bass_unabbreviated" && content.raw_figured_bass != null) {
    answer = content.raw_figured_bass;
  } else if (analysisType === "figured_bass" && content.figured_bass != null) {
    answer = content.figured_bass;
  } else if (content.roman_numeral) {
    answer = LabelLogic.stripFiguredBassTokens(content.roman_numeral);
  } else if (content.pop_symbol) {
    answer = content.pop_symbol;
  } else if (content.figured_bass != null) {
    answer = content.figured_bass;
  } else if (content.functional_label) {
    answer = content.functional_label;
  }

  return LabelLogic.normalizeAnalysisLabel(answer);
}
