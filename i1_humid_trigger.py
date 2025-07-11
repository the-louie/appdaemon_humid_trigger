"""
HumidTrigger AppDaemon App for Home Assistant

This app monitors humidity and temperature sensors to automatically control
switches based on humidity thresholds and minimum temperature requirements.

Copyright (c) 2024 the_louie
BSD 2-Clause License - see LICENSE file for details
"""

import time
import json
import logging
from typing import Dict, List, Optional, Any, Union
import appdaemon.plugins.hass.hassapi as hass


class HumidTrigger(hass.Hass):
    """
    AppDaemon app that triggers switches based on humidity and temperature conditions.

    The app monitors humidity and temperature sensors and controls switches based on:
    - Humidity thresholds (low and high values)
    - Minimum temperature requirement
    - Configurable switch states for different humidity ranges

    Configuration example:
    ```yaml
    HumidTrigger:
      module: i1_humid_trigger
      class: HumidTrigger
      sensors:
        humidity: "sensor.room_humid"
        temperature: "sensor.room_temp"
      switches:
        - entity: "switch.room_switch"
          min_temp: 10
          lt:
            state: "off"
            value: 55
          gt:
            state: "on"
            value: 60
    ```
    """

    def initialize(self) -> None:
        """
        Initialize the HumidTrigger app.

        Sets up sensor monitoring and validates configuration.
        Logs extensive information for debugging purposes.
        """
        try:
            self.log("Loading HumidTrigger()", level="INFO")

            # Extract configuration
            self._extract_config()

            # Validate configuration
            if not self._validate_config():
                self.log(" >> HumidTrigger.initialize(): Configuration validation failed", level="ERROR")
                return

            # Set up state listeners
            self._setup_listeners()

            # Log successful initialization
            self.log(f" >> HumidTrigger initialized successfully: {self.humid_sensor}, {self.temp_sensor} ==> {self.switches}", level="INFO")

            # Perform initial state check
            self._check_initial_state()

        except Exception as e:
            self.log(f" >> HumidTrigger.initialize(): Critical error during initialization: {str(e)}", level="ERROR")
            import traceback
            self.log(f" >> Traceback: {traceback.format_exc()}", level="ERROR")

    def _extract_config(self) -> None:
        """
        Extract and store configuration from args with sane defaults.

        Raises:
            KeyError: If required configuration is missing
        """
        try:
            self.log(" >> Extracting configuration...", level="DEBUG")

            # Extract sensors with defaults
            sensors_config = self.args.get("sensors", {})
            self.humid_sensor = sensors_config.get("humidity")
            self.temp_sensor = sensors_config.get("temperature")

            # Extract switches with defaults
            self.switches = self.args.get("switches", [])

            # Apply defaults to switch configurations
            self._apply_switch_defaults()

            self.log(f" >> Configuration extracted - Humidity: {self.humid_sensor}, Temperature: {self.temp_sensor}, Switches: {len(self.switches)}", level="DEBUG")

        except Exception as e:
            self.log(f" >> _extract_config(): Error extracting configuration: {str(e)}", level="ERROR")
            raise

    def _apply_switch_defaults(self) -> None:
        """
        Apply sane defaults to switch configurations.

        Defaults applied:
        - min_temp: 5°C (prevent operation in freezing conditions)
        - lt.value: 45% (turn off when humidity is low)
        - lt.state: "off" (default off state for low humidity)
        - gt.value: 60% (turn on when humidity is high)
        - gt.state: "on" (default on state for high humidity)
        """
        try:
            self.log(" >> Applying switch defaults...", level="DEBUG")

            for i, switch in enumerate(self.switches):
                # Set default minimum temperature (5°C to prevent freezing)
                if 'min_temp' not in switch:
                    switch['min_temp'] = 5.0
                    self.log(f" >> Switch {i}: Applied default min_temp: 5.0°C", level="DEBUG")

                # Set default low threshold (lt) configuration
                if 'lt' not in switch:
                    switch['lt'] = {}
                if 'value' not in switch['lt']:
                    switch['lt']['value'] = 45.0
                    self.log(f" >> Switch {i}: Applied default lt.value: 45.0%", level="DEBUG")
                if 'state' not in switch['lt']:
                    switch['lt']['state'] = "off"
                    self.log(f" >> Switch {i}: Applied default lt.state: off", level="DEBUG")

                # Set default high threshold (gt) configuration
                if 'gt' not in switch:
                    switch['gt'] = {}
                if 'value' not in switch['gt']:
                    switch['gt']['value'] = 60.0
                    self.log(f" >> Switch {i}: Applied default gt.value: 60.0%", level="DEBUG")
                if 'state' not in switch['gt']:
                    switch['gt']['state'] = "on"
                    self.log(f" >> Switch {i}: Applied default gt.state: on", level="DEBUG")

                # Ensure entity is present (required field)
                if 'entity' not in switch:
                    self.log(f" >> Switch {i}: WARNING - No entity specified, this switch will be skipped", level="WARNING")
                    switch['entity'] = None

            self.log(" >> Switch defaults applied successfully", level="DEBUG")

        except Exception as e:
            self.log(f" >> _apply_switch_defaults(): Error applying defaults: {str(e)}", level="ERROR")

    def _validate_config(self) -> bool:
        """
        Validate the configuration parameters.

        Returns:
            bool: True if configuration is valid, False otherwise
        """
        try:
            self.log(" >> Validating configuration...", level="DEBUG")

            # Check if sensors are configured
            if self.humid_sensor is None:
                self.log(" >> _validate_config(): Humidity sensor not configured", level="ERROR")
                return False

            if self.temp_sensor is None:
                self.log(" >> _validate_config(): Temperature sensor not configured", level="ERROR")
                return False

            # Ensure switches is a list
            if not isinstance(self.switches, list):
                self.log(" >> _validate_config(): Converting switches to list", level="WARNING")
                self.switches = [self.switches] if self.switches else []

            # Validate each switch configuration
            for i, switch in enumerate(self.switches):
                if not self._validate_switch_config(switch, i):
                    return False

            self.log(" >> Configuration validation successful", level="DEBUG")
            return True

        except Exception as e:
            self.log(f" >> _validate_config(): Error during validation: {str(e)}", level="ERROR")
            return False

    def _validate_switch_config(self, switch: Dict[str, Any], index: int) -> bool:
        """
        Validate individual switch configuration.

        Args:
            switch: Switch configuration dictionary
            index: Index of the switch in the list

        Returns:
            bool: True if switch configuration is valid
        """
        try:
            # Check if entity is present and valid
            entity = switch.get('entity')
            if entity is None:
                self.log(f" >> _validate_switch_config(): Switch {index} has no entity specified - skipping", level="WARNING")
                return False

            # Validate lt and gt sub-configurations
            lt_config = switch.get('lt', {})
            gt_config = switch.get('gt', {})

            if not all(key in lt_config for key in ['state', 'value']):
                self.log(f" >> _validate_switch_config(): Switch {index} has invalid 'lt' configuration", level="ERROR")
                return False

            if not all(key in gt_config for key in ['state', 'value']):
                self.log(f" >> _validate_switch_config(): Switch {index} has invalid 'gt' configuration", level="ERROR")
                return False

            # Validate numeric values
            try:
                lt_value = lt_config.get('value')
                gt_value = gt_config.get('value')
                min_temp = switch.get('min_temp')

                if lt_value is None or gt_value is None or min_temp is None:
                    self.log(f" >> _validate_switch_config(): Switch {index} has None values for numeric fields", level="ERROR")
                    return False

                float(lt_value)
                float(gt_value)
                float(min_temp)
            except (ValueError, TypeError):
                self.log(f" >> _validate_switch_config(): Switch {index} has invalid numeric values", level="ERROR")
                return False

            self.log(f" >> Switch {index} configuration validated successfully", level="DEBUG")
            return True

        except Exception as e:
            self.log(f" >> _validate_switch_config(): Error validating switch {index}: {str(e)}", level="ERROR")
            return False

    def _setup_listeners(self) -> None:
        """
        Set up state change listeners for humidity and temperature sensors.
        """
        try:
            self.log(" >> Setting up state listeners...", level="DEBUG")

            # Listen for humidity changes
            self.listen_state(self._state_change_humid, self.humid_sensor)
            self.log(f" >> Humidity listener registered for: {self.humid_sensor}", level="DEBUG")

            # Listen for temperature changes
            self.listen_state(self._state_change_temp, self.temp_sensor)
            self.log(f" >> Temperature listener registered for: {self.temp_sensor}", level="DEBUG")

        except Exception as e:
            self.log(f" >> _setup_listeners(): Error setting up listeners: {str(e)}", level="ERROR")
            raise

    def _check_initial_state(self) -> None:
        """
        Perform initial state check with current sensor values.
        """
        try:
            self.log(" >> Performing initial state check...", level="DEBUG")

            current_humid = self.get_state(self.humid_sensor)
            current_temp = self.get_state(self.temp_sensor)

            self.log(f" >> Initial values - Humidity: {current_humid}, Temperature: {current_temp}", level="DEBUG")

            self._check_state(current_humid, current_temp)

        except Exception as e:
            self.log(f" >> _check_initial_state(): Error during initial state check: {str(e)}", level="ERROR")

    def _state_change_humid(self, entity: str, attribute: str, old_humid: str, new_humid: str, kwargs: Dict[str, Any]) -> None:
        """
        Handle humidity sensor state changes.

        Args:
            entity: The entity that changed
            attribute: The attribute that changed
            old_humid: Previous humidity value
            new_humid: New humidity value
            kwargs: Additional keyword arguments
        """
        try:
            self.log(f" >> Humidity state change: {old_humid} -> {new_humid}", level="DEBUG")

            # Skip if values are the same or invalid
            if new_humid == old_humid or new_humid is None or new_humid == 'unavailable':
                self.log(" >> Skipping humidity change - no meaningful change", level="DEBUG")
                return

            # Get current temperature
            new_temp = self.get_state(self.temp_sensor)
            if new_temp is None or new_temp == 'unavailable':
                self.log(" >> Skipping humidity change - temperature unavailable", level="WARNING")
                return

            self.log(f" >> Processing humidity change with temperature: {new_temp}", level="DEBUG")
            self._check_state(new_humid, new_temp)

        except Exception as e:
            self.log(f" >> _state_change_humid(): Error processing humidity change: {str(e)}", level="ERROR")

    def _state_change_temp(self, entity: str, attribute: str, old_temp: str, new_temp: str, kwargs: Dict[str, Any]) -> None:
        """
        Handle temperature sensor state changes.

        Args:
            entity: The entity that changed
            attribute: The attribute that changed
            old_temp: Previous temperature value
            new_temp: New temperature value
            kwargs: Additional keyword arguments
        """
        try:
            self.log(f" >> Temperature state change: {old_temp} -> {new_temp}", level="DEBUG")

            # Skip if values are the same or invalid
            if new_temp == old_temp or new_temp is None or new_temp == 'unavailable':
                self.log(" >> Skipping temperature change - no meaningful change", level="DEBUG")
                return

            # Get current humidity
            new_humid = self.get_state(self.humid_sensor)
            if new_humid is None or new_humid == 'unavailable':
                self.log(" >> Skipping temperature change - humidity unavailable", level="WARNING")
                return

            self.log(f" >> Processing temperature change with humidity: {new_humid}", level="DEBUG")
            self._check_state(new_humid, new_temp)

        except Exception as e:
            self.log(f" >> _state_change_temp(): Error processing temperature change: {str(e)}", level="ERROR")

    def _check_state(self, humid: str, temp: str) -> None:
        """
        Check current humidity and temperature against configured thresholds.

        Args:
            humid: Current humidity value
            temp: Current temperature value
        """
        try:
            # Validate input values
            if humid is None or humid == 'unavailable':
                self.log(" >> _check_state(): Humidity value is unavailable", level="WARNING")
                return

            if temp is None or temp == 'unavailable':
                self.log(" >> _check_state(): Temperature value is unavailable", level="WARNING")
                return

            # Convert to float for comparison
            try:
                humid_float = float(humid)
                temp_float = float(temp)
            except (ValueError, TypeError) as e:
                self.log(f" >> _check_state(): Error converting values to float: {str(e)}", level="ERROR")
                return

            self.log(f" >> Checking state - Humidity: {humid_float}%, Temperature: {temp_float}°C", level="INFO")

            # Process each switch
            for i, switch in enumerate(self.switches):
                self._process_switch(switch, humid_float, temp_float, i)

        except Exception as e:
            self.log(f" >> _check_state(): Error during state check: {str(e)}", level="ERROR")

    def _process_switch(self, switch: Dict[str, Any], humid: float, temp: float, switch_index: int) -> None:
        """
        Process a single switch based on current humidity and temperature.

        Args:
            switch: Switch configuration dictionary
            humid: Current humidity value
            temp: Current temperature value
            switch_index: Index of the switch for logging
        """
        try:
            # Extract switch configuration
            entity = switch.get('entity')
            min_temp = switch.get('min_temp')
            lt_config = switch.get('lt', {})
            gt_config = switch.get('gt', {})

            lt_value = lt_config.get('value')
            gt_value = gt_config.get('value')
            lt_state = lt_config.get('state')
            gt_state = gt_config.get('state')

            # Validate required values
            if entity is None:
                self.log(f" >> Switch {switch_index}: No entity specified - skipping", level="WARNING")
                return

            if min_temp is None or lt_value is None or gt_value is None:
                self.log(f" >> Switch {switch_index}: Missing required numeric values - skipping", level="ERROR")
                return

            self.log(f" >> Processing switch {switch_index}: {entity}", level="DEBUG")

            # Check minimum temperature requirement
            try:
                min_temp_float = float(min_temp)
                if temp < min_temp_float:
                    self.log(f" >> Switch {switch_index}: Temperature too low ({temp}°C < {min_temp_float}°C) - skipping", level="INFO")
                    return
            except (ValueError, TypeError) as e:
                self.log(f" >> Switch {switch_index}: Error processing minimum temperature: {str(e)}", level="ERROR")
                return

            # Validate threshold values
            try:
                lt_value_float = float(lt_value)
                gt_value_float = float(gt_value)
            except (ValueError, TypeError) as e:
                self.log(f" >> Switch {switch_index}: Error converting threshold values: {str(e)}", level="ERROR")
                return

            # Determine new state based on humidity
            new_state = None
            if humid < lt_value_float:
                self.log(f" >> Switch {switch_index}: Humidity {humid}% < {lt_value_float}% -> {lt_state}", level="INFO")
                new_state = lt_state
            elif humid > gt_value_float:
                self.log(f" >> Switch {switch_index}: Humidity {humid}% > {gt_value_float}% -> {gt_state}", level="INFO")
                new_state = gt_state
            else:
                self.log(f" >> Switch {switch_index}: Humidity {humid}% within range [{lt_value_float}%, {gt_value_float}%] - no change", level="DEBUG")
                new_state = None

            # Apply the new state
            if new_state is not None:
                self._apply_switch_state(entity, new_state, switch_index)

        except Exception as e:
            self.log(f" >> _process_switch(): Error processing switch {switch_index}: {str(e)}", level="ERROR")

    def _apply_switch_state(self, entity: str, state: str, switch_index: int) -> None:
        """
        Apply the new state to a switch.

        Args:
            entity: The entity to control
            state: The new state to apply ('on' or 'off')
            switch_index: Index of the switch for logging
        """
        try:
            current_state = self.get_state(entity)
            self.log(f" >> Switch {switch_index}: Current state: {current_state}, Target state: {state}", level="DEBUG")

            if state == "off":
                self.turn_off(entity)
                self.log(f" >> Switch {switch_index}: Turned OFF {entity}", level="INFO")
            elif state == "on":
                self.turn_on(entity)
                self.log(f" >> Switch {switch_index}: Turned ON {entity}", level="INFO")
            else:
                self.log(f" >> Switch {switch_index}: Unknown state '{state}' for {entity}", level="WARNING")

        except Exception as e:
            self.log(f" >> _apply_switch_state(): Error applying state '{state}' to {entity}: {str(e)}", level="ERROR")

