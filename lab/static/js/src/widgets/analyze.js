/* global define:false */
define([
	'lodash', 
	'jquery', 
	'microevent',
	'app/config'
], function(
	_,
	$,
	MicroEvent,
	Config
) {
	"use strict";

	var ANALYSIS_SETTINGS = Config.get('general.analysisSettings');

	var AnalyzeWidget = function(settings) {
		settings = settings || {};
		this.el = $('<div class="menu-widgets" style="display:inline-block;padding-right:1em"></div>');
		this.state = _.merge(_.cloneDeep(ANALYSIS_SETTINGS), settings);
		this.init();
	};

	_.extend(AnalyzeWidget.prototype, {
		templateHTML: [
			'<fieldset class="settings-notation" style="margin-top:0px">',
				'<legend><label><input type="checkbox" name="analysis_enabled" value="1" accesskey="a"> ANALYZE</label></legend>',
				'<ul>',
				'<li>',
					'<label><input type="checkbox" name="analysis_note_names" value="note_names" accesskey="l"> Letters</label>',
				'</li>',
				'<li>',
					'<label><input type="checkbox" name="analysis_scientific_pitch" value="scientific_pitch" accesskey="s"> Scientific pitch</label>',
				'</li>',
				'<li>',
					'<label><input type="checkbox" name="analysis_fixed_do" value="fixed_do" accesskey="f"> Fixed-do</label>',
				'</li>',
				'<li>',
					'<label><input type="checkbox" name="analysis_pitch_class" value="pitch_class" accesskey="p"> Pitch class</label>',
				'</li>',
				'<li>',
					'<label><input type="checkbox" name="analysis_degrees" value="scale_degrees" accesskey="d"> Degrees</label>',
				'</li>',
				'<li>',
					'<label><input type="checkbox" name="analysis_solfege" value="solfege"  accesskey="m"> Movable-do</label>',
				'</li>',
				'<li>',
					'<label><input type="checkbox" name="analysis_intervals" value="intervals" accesskey="i"> Intervals</label>',
				'</li>',
				'<li>',
					'<label><input type="checkbox" name="analysis_pci" value="pci"> Pitch-class intervals</label>',
				'</li>',
				'<li>',
					'<label><input type="checkbox" name="analysis_chords" value="chord_labels"> Chord labels (A)</label>',
				'</li>',
				'<li>',
					'<label><input type="checkbox" name="analysis_harmony" value="roman_numerals" accesskey="h"> Harmony in Roman numerals</label>',
				'</li>',
				'<li>',
					'<label><input type="checkbox" name="analysis_thoroughbass" value="thoroughbass" accesskey="g"> Figured bass (G) as harmony</label>',
				'</li>',
				'<li>',
					'<label><input type="checkbox" name="analysis_abbreviate_thoroughbass" value="abbreviate_thoroughbass" accesskey="v"> Abbreviate figured bass (V)</label>',
				'</li>',
				'</ul>',
			'</fieldset>'
		].join(''),
		init: function() {
			this.initListeners();
		},
		initListeners: function() {
			var that = this;
			this.el.on('change', 'input', null, function(e) {
				var target_name = e.target.name;
				if (target_name in that.handlers) {
					that.handlers[target_name].call(that, e);
				}
				e.stopPropagation();
			});
		},
		handlers: {
			analysis_enabled: function(e) {
				this.state.enabled = e.target.checked;
				this.trigger('changeCategory', 'analyze', this.state.enabled);
				this.el.find('input').not('input[name=analysis_enabled]').attr('disabled', !this.state.enabled);
			},
			analysis_abbreviate_thoroughbass: function(e) {
				var opt = e.target.value;
				this.state.mode[opt] = e.target.checked;
				this.trigger('changeOption', 'analyze', opt, this.state.mode[opt]);
				document.getElementById('staff').focus();
			},
			/* FIX ME: the next four functions are identical; consolidate them */
			analysis_note_names: function(e) {
				let sel = e.target.value;
				this.state.mode[sel] = e.target.checked;

				var opts = ['scientific_pitch', 'fixed_do', 'note_names', 'pitch_class'];
				if (!opts.includes(sel)) {
					console.log("Error");
					return null;
				}

				if (this.state.mode[sel] === true) {
					this.trigger('changeOption', 'analyze', sel, true);
					var i, len;
					for (var i = 0, len = opts.length; i < len; i++) {
						let opt = opts[i];
						if (opt === sel) continue;
						document.getElementsByName('analysis_' + opt)[0].checked = false;
						this.trigger('changeOption', 'analyze', opt, false);
					}
				} else if (this.state.mode[sel] === false) {
					this.trigger('changeOption', 'analyze', sel, false);
				}
			},
			analysis_fixed_do: function(e) {
				let sel = e.target.value;
				this.state.mode[sel] = e.target.checked;

				var opts = ['scientific_pitch', 'fixed_do', 'note_names', 'pitch_class'];
				if (!opts.includes(sel)) {
					console.log("Error");
					return null;
				}

				if (this.state.mode[sel] === true) {
					this.trigger('changeOption', 'analyze', sel, true);
					var i, len;
					for (var i = 0, len = opts.length; i < len; i++) {
						let opt = opts[i];
						if (opt === sel) continue;
						document.getElementsByName('analysis_' + opt)[0].checked = false;
						this.trigger('changeOption', 'analyze', opt, false);
					}
				} else if (this.state.mode[sel] === false) {
					this.trigger('changeOption', 'analyze', sel, false);
				}
			},
			analysis_pitch_class: function(e) {
				let sel = e.target.value;
				this.state.mode[sel] = e.target.checked;

				var opts = ['scientific_pitch', 'fixed_do', 'note_names', 'pitch_class'];
				if (!opts.includes(sel)) {
					console.log("Error");
					return null;
				}

				if (this.state.mode[sel] === true) {
					this.trigger('changeOption', 'analyze', sel, true);
					var i, len;
					for (var i = 0, len = opts.length; i < len; i++) {
						let opt = opts[i];
						if (opt === sel) continue;
						document.getElementsByName('analysis_' + opt)[0].checked = false;
						this.trigger('changeOption', 'analyze', opt, false);
					}
				} else if (this.state.mode[sel] === false) {
					this.trigger('changeOption', 'analyze', sel, false);
				}
			},
			analysis_scientific_pitch: function(e) {
				let sel = e.target.value;
				this.state.mode[sel] = e.target.checked;

				var opts = ['scientific_pitch', 'fixed_do', 'note_names', 'pitch_class'];
				if (!opts.includes(sel)) {
					console.log("Error");
					return null;
				}

				if (this.state.mode[sel] === true) {
					this.trigger('changeOption', 'analyze', sel, true);
					var i, len;
					for (var i = 0, len = opts.length; i < len; i++) {
						let opt = opts[i];
						if (opt === sel) continue;
						document.getElementsByName('analysis_' + opt)[0].checked = false;
						this.trigger('changeOption', 'analyze', opt, false);
					}
				} else if (this.state.mode[sel] === false) {
					this.trigger('changeOption', 'analyze', sel, false);
				}
			},
			analysis_solfege: function(e) {
				var opt = e.target.value;
				this.state.mode[opt] = e.target.checked;
				var altBox = 'analysis_degrees';
				var altOpt = 'scale_degrees';
				if (this.state.mode[opt] === true && document.getElementsByName(altBox)[0].checked === false){
					this.trigger('changeOption', 'analyze', opt, true);
				}else if (this.state.mode[opt] === true && document.getElementsByName(altBox)[0].checked === true){
					document.getElementsByName(altBox)[0].checked = false;
					this.trigger('changeOption', 'analyze', opt, true);
					this.trigger('changeOption', 'analyze', altOpt, false);
				}else if (this.state.mode[opt] === false){
					this.trigger('changeOption', 'analyze', opt, false);
				}else {
					alert('ERROR');
				}
			},
			analysis_degrees: function(e) {
				var opt = e.target.value;
				this.state.mode[opt] = e.target.checked;
				var altBox = 'analysis_solfege';
				var altOpt = 'solfege';
				if (this.state.mode[opt] === true && document.getElementsByName(altBox)[0].checked === false){
					this.trigger('changeOption', 'analyze', opt, true);
				}else if (this.state.mode[opt] === true && document.getElementsByName(altBox)[0].checked === true){
					document.getElementsByName(altBox)[0].checked = false;
					this.trigger('changeOption', 'analyze', opt, true);
					this.trigger('changeOption', 'analyze', altOpt, false);
				}else if (this.state.mode[opt] === false){
					this.trigger('changeOption', 'analyze', opt, false);
				}else {
					alert('ERROR');
				}
			},
			/* FIX: consolidate next two functions */
			analysis_intervals: function(e) {
				let sel = e.target.value;
				this.state.mode[sel] = e.target.checked;

				var opts = ['intervals', 'pci']; // N.B.
				if (!opts.includes(sel)) {
					console.log("Error");
					return null;
				}

				if (this.state.mode[sel] === true) {
					this.trigger('changeOption', 'analyze', sel, true);
					var i, len;
					for (var i = 0, len = opts.length; i < len; i++) {
						let opt = opts[i];
						if (opt === sel) continue;
						document.getElementsByName('analysis_' + opt)[0].checked = false;
						this.trigger('changeOption', 'analyze', opt, false);
					}
				} else if (this.state.mode[sel] === false) {
					this.trigger('changeOption', 'analyze', sel, false);
				}
			},
			analysis_pci: function(e) {
				let sel = e.target.value;
				this.state.mode[sel] = e.target.checked;

				var opts = ['intervals', 'pci']; // N.B.
				if (!opts.includes(sel)) {
					console.log("Error");
					return null;
				}

				if (this.state.mode[sel] === true) {
					this.trigger('changeOption', 'analyze', sel, true);
					var i, len;
					for (var i = 0, len = opts.length; i < len; i++) {
						let opt = opts[i];
						if (opt === sel) continue;
						document.getElementsByName('analysis_' + opt)[0].checked = false;
						this.trigger('changeOption', 'analyze', opt, false);
					}
				} else if (this.state.mode[sel] === false) {
					this.trigger('changeOption', 'analyze', sel, false);
				}
			},
			/* FIX: consolidate next three functions */
			analysis_harmony: function(e) {
				var opt = e.target.value;
				this.state.mode[opt] = e.target.checked;
				this.trigger('changeOption', 'analyze', opt, this.state.mode[opt]);
				document.getElementById('staff').focus();
			},
			analysis_chords: function(e) {
				var opt = e.target.value;
				this.state.mode[opt] = e.target.checked;
				this.trigger('changeOption', 'analyze', opt, this.state.mode[opt]);
				document.getElementById('staff').focus();
			},
			analysis_thoroughbass: function(e) {
				var opt = e.target.value;
				this.state.mode[opt] = e.target.checked;
				this.trigger('changeOption', 'analyze', opt, this.state.mode[opt]);
				document.getElementById('staff').focus();
			}
		},
		render: function() {
			var that = this;
			
			// update the element content
			this.el.html(this.templateHTML);
			
			// update the input states
			this.el.find('input[name=analysis_enabled]')[0].checked = this.state.enabled;
			$.each(this.state.mode, function(key, val) {
				var $input = that.el.find('input[value='+key+']');
				$input.attr('checked', val ? true : false);
				$input.attr('disabled', !that.state.enabled);
			});
			
			// set the "neither" option
			if (!this._eitherModeTrue('note_names', 'scientific_pitch')) { 
				this.el.find('input[value=neither][name=note_analysis]').attr('checked', true).attr('disabled', !this.state.enabled);
			}
			// if (!this._eitherModeTrue('scale_degrees', 'solfege')) {
			// 	this.el.find('input[value=neither][name=melodic_analysis]').attr('checked', true).attr('disabled', !this.state.enabled);
			// }

			return this;
		},
		getState: function() {
			return this.state;
		},
		_eitherModeTrue: function(a, b) {
			return this.state.mode[a] || this.state.mode[b];
		},

	});

	MicroEvent.mixin(AnalyzeWidget);

	return AnalyzeWidget;
});
