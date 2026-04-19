define(["jquery", "lodash"], function ($, _) {
  "use strict";

  /**
   * SkillMap component for visualizing the knowledge graph using Cytoscape.js.
   */
  var SkillMap = {
    /**
     * Initializes the skill map.
     * @param {Object} options
     * @param {HTMLElement} options.container - The element to render the graph in.
     * @param {string} options.dataUrl - The API endpoint for graph elements.
     * @param {string} options.courseId - Optional course filter.
     */
    init: function (options) {
      this.container = options.container;
      this.dataUrl = options.dataUrl;
      this.courseId = options.courseId;
      this.load();
    },

    /**
     * Fetches graph data from the server.
     */
    load: function () {
      var self = this;
      $.ajax({
        url: this.dataUrl,
        method: "GET",
        dataType: "json",
        success: function (response) {
          self.render(response.elements);
        },
        error: function (xhr, status, error) {
          console.error("Failed to load skill map data:", error);
        }
      });
    },

    /**
     * Renders the graph using Cytoscape.js.
     * @param {Array} elements - Nodes and edges.
     */
    render: function (elements) {
      var self = this;
      
      // Ensure Cytoscape and extensions are available
      if (typeof cytoscape === 'undefined') {
          console.error("Cytoscape.js not found.");
          return;
      }

      // Register dagre layout extension if available globally
      if (typeof window.cytoscapeDagre !== 'undefined' && typeof window.dagre !== 'undefined') {
          cytoscape.use(window.cytoscapeDagre);
      }

      this.cy = cytoscape({
        container: this.container,
        elements: elements,
        boxSelectionEnabled: false,
        autounselectify: false,
        style: [
          {
            selector: "node",
            style: {
              "label": "data(label)",
              "text-valign": "center",
              "text-halign": "center",
              "width": 140,
              "height": 45,
              "shape": "round-rectangle",
              "background-color": function (ele) {
                var level = ele.data("level");
                if (ele.data("is_decayed")) return "#e74c3c"; // Red for decay
                switch (level) {
                  case "mastered": return "#27ae60";
                  case "proficient": return "#2980b9";
                  case "familiar": return "#f1c40f";
                  default: return "#ecf0f1";
                }
              },
              "color": function (ele) {
                var level = ele.data("level");
                return (level === "not_started" && !ele.data("is_decayed")) ? "#7f8c8d" : "#fff";
              },
              "font-size": "11px",
              "font-weight": "bold",
              "text-wrap": "wrap",
              "text-max-width": "120px",
              "border-width": 1,
              "border-color": "#bdc3c7",
              "opacity": function (ele) {
                return ele.data("unlocked") ? 1.0 : 0.4;
              },
              "ghost": "yes",
              "ghost-offset-x": 2,
              "ghost-offset-y": 2,
              "ghost-opacity": 0.1
            },
          },
          {
            selector: "edge",
            style: {
              "width": 3,
              "line-color": "#dcdde1",
              "target-arrow-color": "#dcdde1",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
              "arrow-scale": 1.2
            },
          },
          {
            selector: "node:selected",
            style: {
              "border-width": 4,
              "border-color": "#34495e",
              "overlay-opacity": 0.1
            },
          },
        ],
        layout: {
          name: "dagre",
          rankDir: "LR",
          nodeSep: 40,
          rankSep: 80,
          padding: 50,
          animate: true,
          animationDuration: 500
        },
      });

      // Selection handling
      this.cy.on("select", "node", function (evt) {
        self.showInfo(evt.target.data());
      });

      this.cy.on("unselect", "node", function () {
        $("#skill-info-panel").fadeOut(200);
      });
      
      // Zoom and Pan constraints
      this.cy.minZoom(0.3);
      this.cy.maxZoom(2.0);
    },

    /**
     * Updates the info panel with selected skill details.
     * @param {Object} data - Node data.
     */
    showInfo: function (data) {
      $("#panel-skill-name").text(data.label);
      $("#panel-mastery-level")
        .text(data.is_decayed ? "Review Due" : data.level.replace("_", " "))
        .css({
            "background-color": this.getLevelColor(data.level, data.is_decayed),
            "color": (data.level === "not_started" && !data.is_decayed) ? "#555" : "white",
            "border": (data.level === "not_started") ? "1px solid #ddd" : "none"
        });
      
      var description = "This skill involves dynamic music theory analysis related to " + data.label.toLowerCase() + ".";
      if (!data.unlocked) {
          description += " \n\n🔒 Prerequisites required! Master the preceding skills to unlock this path.";
      } else if (data.is_decayed) {
          description += " \n\n⚠️ It's been a while! Practice this skill now to restore your mastery.";
      }
      $("#panel-description").text(description);

      // Link to adaptive entry point
      // In a real implementation, we would want to find the specific playlist 
      // that introduces this skill. For the MVP, we use the general adaptive route.
      var practiceUrl = "/lab/playlists/adaptive/";
      if (this.courseId) {
          practiceUrl = "/lab/playlists/" + this.courseId + "/adaptive/";
      }
      
      if (data.unlocked) {
          $("#panel-practice-link").attr("href", practiceUrl).show();
          $("#panel-practice-link").text(data.is_decayed ? "Start Review" : "Practice This Skill");
      } else {
          $("#panel-practice-link").hide();
      }

      $("#skill-info-panel").stop().fadeIn(300);
    },

    /**
     * Helper to get CSS color for a mastery level.
     */
    getLevelColor: function(level, is_decayed) {
        if (is_decayed) return "#e74c3c";
        switch (level) {
            case "mastered": return "#27ae60";
            case "proficient": return "#2980b9";
            case "familiar": return "#f1c40f";
            default: return "#ecf0f1";
        }
    }
  };

  return SkillMap;
});
