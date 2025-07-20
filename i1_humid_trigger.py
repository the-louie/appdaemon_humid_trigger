"""
HumidTrigger AppDaemon App for Home Assistant

This app monitors humidity and temperature sensors to automatically control
switches based on humidity thresholds and minimum temperature requirements.

Copyright (c) 2024 the_louie
BSD 2-Clause License - see LICENSE file for details
"""

import appdaemon.plugins.hass.hassapi as hass
import traceback


class HumidTrigger(hass.Hass):
    """AppDaemon app that triggers switches based on humidity and temperature conditions."""

    def initialize(self):
        """Initialize the HumidTrigger app."""
        try:
            # Extract and validate configuration
            sensors = self.args.get("sensors", {})
            self.humid_sensor = sensors.get("humidity")
            self.temp_sensor = sensors.get("temperature")
            self.switches = self.args.get("switches", [])

            if not self.humid_sensor or not self.temp_sensor:
                self.log("Humidity or temperature sensor not configured", level="ERROR")
                return

            if not isinstance(self.switches, list):
                self.switches = [self.switches] if self.switches else []

            # Apply defaults and validate switches
            for i, switch in enumerate(self.switches):
                if 'entity' not in switch:
                    self.log(f"Switch {i}: No entity specified - skipping", level="WARNING")
                    continue

                # Apply defaults
                switch.setdefault('min_temp', 5.0)
                switch.setdefault('lt', {}).setdefault('value', 45.0)
                switch.setdefault('lt', {}).setdefault('state', 'off')
                switch.setdefault('gt', {}).setdefault('value', 60.0)
                switch.setdefault('gt', {}).setdefault('state', 'on')

                # Validate required fields
                if not all(key in switch['lt'] for key in ['state', 'value']):
                    self.log(f"Switch {i}: Invalid 'lt' configuration", level="ERROR")
                    continue
                if not all(key in switch['gt'] for key in ['state', 'value']):
                    self.log(f"Switch {i}: Invalid 'gt' configuration", level="ERROR")
                    continue

                # Validate numeric values
                try:
                    float(switch['min_temp'])
                    float(switch['lt']['value'])
                    float(switch['gt']['value'])
                except (ValueError, TypeError) as e:
                    self.log(f"Switch {i}: Invalid numeric values - {str(e)}", level="ERROR")
                    continue

            # Set up listeners
            self.listen_state(self._state_change_humid, self.humid_sensor)
            self.listen_state(self._state_change_temp, self.temp_sensor)

            self.log(f"HumidTrigger initialized: {self.humid_sensor}, {self.temp_sensor} ==> {len(self.switches)} switches", level="INFO")

            # Initial state check
            self._check_state()

        except Exception as e:
            self.log(f"Critical error during initialization: {str(e)}", level="ERROR")
            self.log(f"Traceback: {traceback.format_exc()}", level="ERROR")

    def _state_change_humid(self, entity, attribute, old_humid, new_humid, kwargs):
        """Handle humidity sensor state changes."""
        try:
            if new_humid != old_humid and new_humid not in (None, 'unavailable'):
                self._check_state()
        except Exception as e:
            self.log(f"Error in humidity state change handler: {str(e)}", level="ERROR")
            self.log(f"Traceback: {traceback.format_exc()}", level="ERROR")

    def _state_change_temp(self, entity, attribute, old_temp, new_temp, kwargs):
        """Handle temperature sensor state changes."""
        try:
            if new_temp != old_temp and new_temp not in (None, 'unavailable'):
                self._check_state()
        except Exception as e:
            self.log(f"Error in temperature state change handler: {str(e)}", level="ERROR")
            self.log(f"Traceback: {traceback.format_exc()}", level="ERROR")

    def _check_state(self):
        """Check current humidity and temperature against configured thresholds."""
        try:
            humid = self.get_state(self.humid_sensor)
            temp = self.get_state(self.temp_sensor)

            if humid in (None, 'unavailable'):
                self.log("Humidity sensor value unavailable", level="WARNING")
                return

            if temp in (None, 'unavailable'):
                self.log("Temperature sensor value unavailable", level="WARNING")
                return

            try:
                humid_float = float(humid)
                temp_float = float(temp)
            except (ValueError, TypeError) as e:
                self.log(f"Error converting sensor values to float: {str(e)}", level="ERROR")
                return

            # Process each switch
            for i, switch in enumerate(self.switches):
                if 'entity' not in switch:
                    continue

                try:
                    min_temp = float(switch['min_temp'])
                    if temp_float < min_temp:
                        self.log(f"Switch {i}: Temperature too low ({temp_float}°C < {min_temp}°C) - skipping", level="INFO")
                        continue

                    lt_value = float(switch['lt']['value'])
                    gt_value = float(switch['gt']['value'])
                    lt_state = switch['lt']['state']
                    gt_state = switch['gt']['state']
                    entity = switch['entity']

                    # Determine new state based on humidity
                    if humid_float < lt_value:
                        self._apply_state(entity, lt_state, i, f"Humidity {humid_float}% < {lt_value}%")
                    elif humid_float > gt_value:
                        self._apply_state(entity, gt_state, i, f"Humidity {humid_float}% > {gt_value}%")

                except (ValueError, TypeError) as e:
                    self.log(f"Switch {i}: Error processing numeric values - {str(e)}", level="ERROR")
                    continue
                except KeyError as e:
                    self.log(f"Switch {i}: Missing required configuration key - {str(e)}", level="ERROR")
                    continue
                except Exception as e:
                    self.log(f"Switch {i}: Unexpected error during processing - {str(e)}", level="ERROR")
                    continue

        except Exception as e:
            self.log(f"Error during state check: {str(e)}", level="ERROR")
            self.log(f"Traceback: {traceback.format_exc()}", level="ERROR")

    def _apply_state(self, entity, state, switch_index, reason):
        """Apply state to switch and log the action."""
        try:
            if state == "off":
                self.turn_off(entity)
                self.log(f"Switch {switch_index}: Turned OFF {entity} ({reason})", level="INFO")
            elif state == "on":
                self.turn_on(entity)
                self.log(f"Switch {switch_index}: Turned ON {entity} ({reason})", level="INFO")
            else:
                self.log(f"Switch {switch_index}: Unknown state '{state}' for {entity}", level="WARNING")
        except Exception as e:
            self.log(f"Error applying state '{state}' to {entity}: {str(e)}", level="ERROR")
            self.log(f"Traceback: {traceback.format_exc()}", level="ERROR")

