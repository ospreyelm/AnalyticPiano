import VexflowRenderConfig from "app/components/music/rendering/vexflow_render_config";
import VexflowMeasureLayout from "app/components/music/rendering/vexflow_measure_layout";
import VexflowRenderPipeline from "app/components/music/rendering/vexflow_render_pipeline";

function render(score, renderer, opts) {
    var ctx = renderer.getContext();

    // Get canvas element - it's stored in ctx.canvas or ctx.element depending on VexFlow version
    var canvas = ctx.canvas || ctx.element;

    // Clear canvas first
    if (canvas) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }

    ctx.save();
    try {
      var cfg = VexflowRenderConfig.buildRenderConfig(score, opts, canvas);
      if (!cfg) return;

      var win = VexflowRenderConfig.selectMeasureWindow(score, opts, cfg);
      if (!win) return;

      var layout = VexflowMeasureLayout.computeMeasureLayout(score, opts, cfg, win);

      VexflowRenderPipeline.renderMeasures(ctx, score, opts, cfg, win, layout);
    } finally {
      ctx.restore();
    }
  }

export default {
  render: render
};
