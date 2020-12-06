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

	var distribution_options = ["keyboard", "chorale", "grandStaff", "LH", "RH", "keyboardPlusRHBias", "keyboardPlusLHBias"]

	var getUrlVars = function() {
		var vars = {};
		var parts = window.location.href.replace(/[?&]+([^=&]+)=([^&]*)/gi, function(m,key,value) {
			vars[key] = value;
		});
		return vars;
	};
	// console.log('URL variables', getUrlVars());

	var STAFF_DISTRIBUTION = Config.get('general.staffDistribution');
	var VOICE_COUNT_FOR_KEYBOARD_STYLE = Config.get('general.voiceCountForKeyboardStyle');

	let url_staff_dist = getUrlVars().hasOwnProperty('staffDistribution');
	let storage_staff_dist = sessionStorage.getItem('staffDistribution');
	let valid_staff_dists = ["keyboard", "chorale", "LH", "RH", "keyboardPlusRHBias", "keyboardPlusLHBias", "grandStaff"];

	if (storage_staff_dist) {
		STAFF_DISTRIBUTION = storage_staff_dist;
	} else if (url_staff_dist && valid_staff_dists.includes(url_staff_dist)) {
		STAFF_DISTRIBUTION = url_staff_dist;
	}

	var StaffDistributionWidget = function(distribution=false) {
		this.el = $('<div></div>');
		this.state = (distribution && ["keyboard","chorale"].includes(distribution) ? distribution : STAFF_DISTRIBUTION);
		// console.log('new widget', this.state);
		this.init();
	};

	_.extend(StaffDistributionWidget.prototype, {
		templateHTML: [
			'<fieldset class="settings-notation">',
				'<legend><label>STAFF DISTRIBUTION</label></legend>',
				'<ul>'].join('') +
				distribution_options.map(
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
			
			// update the element content
			this.el.html(this.templateHTML);
			
			// update the input states
			$.each(distribution_options, function(idx, val) {
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
