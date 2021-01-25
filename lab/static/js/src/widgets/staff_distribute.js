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

	var valid_staff_dists = ["keyboard", "chorale", "grandStaff", "LH", "RH", "keyboardPlusRHBias", "keyboardPlusLHBias"];

	var STAFF_DISTRIBUTION = Config.get('general.staffDistribution');
	var VOICE_COUNT_FOR_KEYBOARD_STYLE = Config.get('general.voiceCountForKeyboardStyle');

	let storage_staff_dist = sessionStorage.getItem('staffDistribution');
	if (storage_staff_dist && valid_staff_dists.includes(storage_staff_dist)) {
		STAFF_DISTRIBUTION = storage_staff_dist;
	}

	var StaffDistributionWidget = function(distribution = false, is_exercise_view = false) {
		this.is_exercise_view = is_exercise_view || false;
		this.el = $('<div class="menu-widgets"></div>');
		this.state = (distribution && valid_staff_dists.includes(distribution) ? distribution : STAFF_DISTRIBUTION);
		// console.log('new widget', this.state);
		this.init();
	};

	_.extend(StaffDistributionWidget.prototype, {
		templateHTML: [
			'<fieldset class="settings-notation">',
				'<legend><label>STAFF DISTRIBUTION</label></legend>',
				'<ul>'].join('') +
				valid_staff_dists.map(
					(opt) =>
					['<li><label><input type="checkbox" name="staff_distribution" value="', opt, '"> ', opt, '</label></li>'].join('')
					).join('') +
				['</ul>',
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
			staff_distribution: function(e) {
				var opt = e.target.value; // e.g. "keyboard"
				this.state = opt;
				/* temporary hack */
				sessionStorage.setItem('staffDistribution', opt);
				if (e.target.checked) {
					this.trigger('changeValue', 'distribute', opt);
				}
				this.render();
			},
		},
		render: function() {
			var that = this;
			
			// update the element content; FAULTY?
			// if (this.is_exercise_view) {
			// 	this.el.html(this.templateHTML.replace(/type="checkbox"/gi, 'type="checkbox" onclick="return false;"'));
			// } else {
			// 	this.el.html(this.templateHTML);
			// }
			this.el.html(this.templateHTML);

			// update the input states
			$.each(valid_staff_dists, function(idx, val) {
				var $input = that.el.find('input[value='+val+']');
				$input.attr('checked', val == that.state ? true : false);
			});
			
			return this;
		},
		getState: function() {
			return this.state;
		},

	});

	MicroEvent.mixin(StaffDistributionWidget);

	return StaffDistributionWidget;
});
