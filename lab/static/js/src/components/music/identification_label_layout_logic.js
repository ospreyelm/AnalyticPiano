

function getKeyLabelPosition(opts) {
    opts = opts || {};
    var slotX = typeof opts.slotX === "number" ? opts.slotX : 0;
    var slotY = typeof opts.slotY === "number" ? opts.slotY : 0;
    var textWidth = Math.max(0, typeof opts.textWidth === "number" ? opts.textWidth : 0);
    var canvasWidth = typeof opts.canvasWidth === "number" ? opts.canvasWidth : null;
    var canvasHeight = typeof opts.canvasHeight === "number" ? opts.canvasHeight : null;
    var initial = opts.initial === true;
    var minX = textWidth / 2 + 8;
    var x = initial ? slotX - Math.max(220, textWidth / 2 + 190) : slotX;

    if (x < minX) x = minX;
    if (canvasWidth !== null) {
      var maxX = canvasWidth - textWidth / 2 - 8;
      if (x > maxX) x = maxX;
    }

    var y = slotY + 34;
    if (canvasHeight !== null) {
      y = Math.min(y, canvasHeight - 10);
    }

    return { x: Math.round(x), y: Math.round(y) };
  }

export default {
  getKeyLabelPosition: getKeyLabelPosition,
};
