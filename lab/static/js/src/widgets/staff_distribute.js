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

    var STAFF_DISTRIBUTION = (getUrlVars().hasOwnProperty('staffDistribution') && distribution_options.includes(getUrlVars()['staffDistribution']) ? getUrlVars()['staffDistribution'] : Config.get('general.staffDistribution'));

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
				if (e.target.checked) {
					var opt = e.target.value;
					this.state = opt;
					this.render();
				}
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
