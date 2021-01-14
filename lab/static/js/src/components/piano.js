define([
	'jquery', 
	'lodash',
	'app/config',
	'app/components/events',
	'app/components/component',
	'./piano/keyboard', 
	'./piano/pedals',
	'./piano/toolbar'
], function(
	$,
	_,
	Config,
	EVENTS,
	Component,
	KeyboardComponent,
	PedalsComponent, 
	ToolbarComponent
) {
	/**
	 * Defines the default keyboard size.
	 * @type {number}
	 * @const
	 */
	var DEFAULT_KEYBOARD_SIZE = Config.get('general.defaultKeyboardSize');

	/** 
	 * ajax call to GET the keyboard size
	 * this will set the keyboard size to user's preference
	 * if no one is logged in the size is 49 (this is defined in apps.views.send_keyboard_size)
	 */

	$.ajax({
		type: 'GET',
		url: this.location.origin + "/ajax/preferences/",
		async: false,
		success: function (response) {
			if(!response["valid"]){
				/** if the call is successful response.instance will hold the json sent by the server 
				 * use the following two lines to log the response to the console
				 * console.log(response);
				 * console.log(JSON.parse(response.instance)); */
				var sticky_settings = JSON.parse(response.instance);
				DEFAULT_KEYBOARD_SIZE = sticky_settings.keyboard_size;
			}
		}
	})

	var DEFAULT_OCTAVE_ADJUSTMENT = Config.get('general.defaultOctaveAdjustment');

	/**
	 * Creates a PianoComponent
	 *
	 * This is responsible for displaying the on-screen piano and
	 * its subcomponents such as the keyboard, pedals, and controls.
	 *
	 * @constructor
	 */
	var PianoComponent = function(settings) {
		this.settings = settings || {};

		var toolbarConfig = {metronome: false};
		var keyboardConfig = {
			numberOfKeys: DEFAULT_KEYBOARD_SIZE,
			octaveAdjustment: DEFAULT_OCTAVE_ADJUSTMENT
		};
		var toolbarEnabled = true;
		var pedalsEnabled = true;

		if("toolbarConfig" in this.settings) {
			toolbarConfig = this.settings.toolbarConfig;
		}
		if("keyboardConfig" in this.settings) {
			keyboardConfig = this.settings.keyboardConfig;
		}
		if("toolbarEnabled" in this.settings) {
			toolbarEnabled = this.settings.toolbarEnabled ? true : false;
		}
		if("pedalsEnabled" in this.settings) {
			pedalsEnabled = this.settings.pedalsEnabled ? true : false;
		}

		if(toolbarEnabled) {
			this.setComponent('toolbar', new ToolbarComponent(toolbarConfig));
		}
		if(pedalsEnabled) {
			this.setComponent('pedals', new PedalsComponent());
		}

		this.setComponent('keyboard', new KeyboardComponent(keyboardConfig));

		_.bindAll(this, ['onKeyboardChange', 'onOctaveChange']);
	};

	PianoComponent.prototype = new Component();

	/**
	 * Initializes the component.
	 *
	 * @return undefined
	 */
	PianoComponent.prototype.initComponent = function() {
		this.el = $('<div class="keyboard-wrapper"></div>');
		this.initListeners();
	};

	/**
	 * Initializes listeners.
	 *
	 * @return undefined
	 */
	PianoComponent.prototype.initListeners = function() {
		this.subscribe(EVENTS.BROADCAST.KEYBOARD_SIZE, this.onKeyboardChange);
		this.subscribe(EVENTS.BROADCAST.OCTAVE_ADJUSTMENT, this.onOctaveChange);
	};
	/**
	 * Removes listeners.
	 *
	 * @return undefined
	 */
	PianoComponent.prototype.removeListeners = function() {
		this.unsubscribe(EVENTS.BROADCAST.KEYBOARD_SIZE, this.onKeyboardChange);
		this.unsubscribe(EVENTS.BROADCAST.OCTAVE_ADJUSTMENT, this.onOctaveChange);
	};

	/**
	 * Renders the toolbar, keyboard, and pedals.
	 *
	 * @return this
	 */
	PianoComponent.prototype.render = function() {
		this.el.empty();
		_.invoke(this.components, "render");
		if(this.hasComponent('toolbar')) {
			this.el.append(this.getComponent('toolbar').el);
		}
		this.el.append(this.getComponent('keyboard').el);
		if(this.hasComponent('pedals')) {
			this.el.append(this.getComponent('pedals').el);
		}
		return this;
	};

	/**
	 * Convenience method to render this object to a 
	 * location on the page given by the selector.
	 *
	 * @param {string|jQuery} selector
	 * @return this
	 */
	PianoComponent.prototype.renderTo = function(selector) {
		$(selector).append(this.render().el);
		this.updateWidth();
		return this;
	};

	/**
	 * Handles a keyboard change event that should change the
	 * size of the keyboard. 
	 *
	 * This involves removing the old keyboard and replacing it
	 * with a new one with the given size.
	 *
	 * @return undefined
	 */
	PianoComponent.prototype.onKeyboardChange = function(numberOfKeys) {
		var oldKeyboardComponent = this.getComponent('keyboard');
		var newKeyboardComponent = new KeyboardComponent({
			numberOfKeys: numberOfKeys,
			octaveAdjustment: oldKeyboardComponent.octaveAdjustment
		});
		newKeyboardComponent.init(this);

		this.removeComponent(oldKeyboardComponent);
		oldKeyboardComponent.destroy();

		this.setComponent('keyboard', newKeyboardComponent);
		this.render();
		this.updateWidth();
	};
	PianoComponent.prototype.onOctaveChange = function(octaveAdjustment) {
		var oldKeyboardComponent = this.getComponent('keyboard');
		var newKeyboardComponent = new KeyboardComponent({
			numberOfKeys: oldKeyboardComponent.numberOfKeys,
			octaveAdjustment: octaveAdjustment
		});
		newKeyboardComponent.init(this);

		this.removeComponent(oldKeyboardComponent);
		oldKeyboardComponent.destroy();

		this.setComponent('keyboard', newKeyboardComponent);
		this.render();
		this.updateWidth();
	};

	/**
	 * Updates the width the piano wrapper element to match
	 * the size of the keyboard element.
	 *
	 * @return undefined
	 */
	PianoComponent.prototype.updateWidth = function() {
		var keyboardComponent = this.getComponent('keyboard');
		var offset = keyboardComponent.keyboardEl.position();
		var total_margin = 2 * offset.left;

		this.el.width(keyboardComponent.layout.width + total_margin);
	};

	return PianoComponent;
});
