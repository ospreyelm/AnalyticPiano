

function getTimeSignatureFontStack() {
    return '"Bravura Text","Finale Maestro Text","Petaluma Script","Noto Music",serif';
  }

  function renderTimeSignatureMarkup(text) {
    var parts = String(text).split("/");
    if (parts.length !== 2) {
      return text;
    }
    return '<span class="meter-ts"><span class="meter-ts-top">' +
      parts[0] +
      '</span><span class="meter-ts-bottom">' +
      parts[1] +
      '</span></span>';
  }

export default {
  getTimeSignatureFontStack: getTimeSignatureFontStack,
    renderTimeSignatureMarkup: renderTimeSignatureMarkup,
};
