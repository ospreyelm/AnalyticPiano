"use strict";

function getMode(definition) {
  return definition.mode ||
    (definition.score &&
      definition.score.umto &&
      definition.score.umto.metadata &&
      definition.score.umto.metadata.mode) ||
    null;
}

function isHarmonization(definition) {
  return getMode(definition) === "harmonization";
}

function getHarmonizationTargets(definition) {
  return definition.harmonizationTargets || [];
}

function getHarmonizationMetadata(definition) {
  return (
    definition.score &&
    definition.score.umto &&
    definition.score.umto.metadata
  ) || {};
}

var exports = {
  getMode: getMode,
  isHarmonization: isHarmonization,
  getHarmonizationTargets: getHarmonizationTargets,
  getHarmonizationMetadata: getHarmonizationMetadata
};

export default exports;
