/* global define:false */
define([
	'lodash', 
	'jquery', 
	'microevent',
	'app/config'
], function(_, $, MicroEvent, Config) {
	"use strict";

	var ANALYSIS_SETTINGS = Config.get('general.analysisSettings');

	var AnalyzeWidget = function(settings) {
		settings = settings || {};
		this.el = $('<div></div>');
		this.state = _.merge(_.cloneDeep(ANALYSIS_SETTINGS), settings);
		this.init();
	};

	_.extend(AnalyzeWidget.prototype, {
		templateHTML: [
			'<fieldset class="settings-notation">',
				'<legend><label><input type="checkbox" name="analysis_enabled" value="1"> Turn on analysis</label></legend>',
				'<ul>',
				'<li>',
					'<label><input type="checkbox" name="harmonic_analysis_roman_numerals" value="roman_numerals"> Harmony</label>',						
					'<label><input type="checkbox" name="harmonic_analysis_intervals" value="intervals"> Intervals</label>',						
				'</li>',
				'<li>',
					'<label><input type="radio" name="note_analysis" value="note_names"> Letters</label>',
					'<label><input type="radio" name="note_analysis" value="scientific_pitch"> Scientific pitch</label>',
					'<label><input type="radio" name="note_analysis" value="neither"> No pitch</label>',
				'</li>',
				'<li>',
					'<label><input type="radio" name="melodic_analysis" value="scale_degrees"> Degrees</label>',
					'<label><input type="radio" name="melodic_analysis" value="solfege" /> Movable-do</label>',
					'<label><input type="radio" name="melodic_analysis" value="neither"> No melody</label>',
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
			note_analysis: function(e) {
				var that = this;
				$.each(['note_names', 'scientific_pitch'], function(index, opt) {
					that.state.mode[opt] = (e.target.value == opt ? true : false);
					that.trigger('changeOption', 'analyze', opt, that.state.mode[opt]);
				});
			},
			melodic_analysis: function(e) {
				var that = this;
				$.each(['scale_degrees', 'solfege'], function(index, opt) {
					that.state.mode[opt] = (e.target.value == opt ? true : false);
					that.trigger('changeOption', 'analyze', opt, that.state.mode[opt]);
				});
			},
			harmonic_analysis_intervals: function(e) {
				var opt = e.target.value;
				this.state.mode.intervals = e.target.checked;
				this.trigger('changeOption', 'analyze', opt, this.state.mode[opt]);
			},
			harmonic_analysis_roman_numerals: function(e) {
				var opt = e.target.value;
				this.state.mode[opt] = e.target.checked;
				this.trigger('changeOption', 'analyze', opt, this.state.mode[opt]);
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
			if (!this._eitherModeTrue('scale_degrees', 'solfege')) {
				this.el.find('input[value=neither][name=melodic_analysis]').attr('checked', true).attr('disabled', !this.state.enabled);
			}

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
