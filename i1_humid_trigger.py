"""
HumidTrigger AppDaemon App for Home Assistant

This app monitors humidity and temperature sensors to automatically control
switches based on humidity thresholds and minimum temperature requirements.

Copyright (c) 2024 the_louie
BSD 2-Clause License - see LICENSE file for details
"""

import appdaemon.plugins.hass.hassapi as hass

import ha_states
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

            # Say so at startup if anything this app drives is not there.
            #
            # The config validation above checks the *shape* of each switch --
            # that it has an `entity` key, a well-formed lt/gt pair, numeric
            # thresholds. It never checked that the entity exists in Home
            # Assistant, so a switch that had been renamed or removed produced
            # a perfectly healthy-looking startup line and then silently drove
            # nothing (T-56). The minivind plug was replaced on 2026-09-03 and
            # `Fönster barnens rum` on 2026-09-05, so a config left pointing at
            # a dead id is a live risk, not a hypothetical one.
            self._report_missing_entities()

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

    # S7-07: the definition is shared estate-wide. The class attribute this
    # replaces was defined in S5-03 and then never consulted -- the methods
    # used their own literals, which is the variant-zoo problem in miniature,
    # committed by the same hand that was fixing it elsewhere.
    NOT_REPORTING = ha_states.HA_UNAVAILABLE_STATES

    def _report_missing_entities(self):
        """Report, at startup, anything this app drives that is not there.

        The distinction is the useful part, and it is the same one S4-08 drew
        for the motion lights:

        **Missing** -- `get_state` returns `None`. The id is wrong or the
        hardware is gone. No amount of waiting fixes it, so it is an ERROR.

        **Unavailable** -- the entity exists and is off the network. A flat
        battery, a plug pulled out. It may well come back, so it is a WARNING.

        Collapsing the two would either cry wolf at every brief dropout or stay
        silent about a config pointing at an entity that no longer exists.

        Returns the list of missing entity ids, so a caller (and a test) can
        see what it found rather than only what it logged.
        """
        missing, unavailable = [], []
        for label, entity in self._driven_entities():
            state = self.get_state(entity)
            if state is None:
                missing.append(entity)
                self.log(
                    "[HT001] {} {} does not exist -- this app will drive "
                    "nothing and will not say so again".format(label, entity),
                    level="ERROR",
                )
            elif ha_states.not_reporting(state):
                unavailable.append(entity)
                self.log(
                    "[HT002] {} {} is {}".format(label, entity, state),
                    level="WARNING",
                )
        if not missing and not unavailable:
            self.log(
                "[HT003] all {} configured entities present".format(
                    len(list(self._driven_entities()))
                )
            )
        return missing

    def _driven_entities(self):
        """Every entity this app reads or writes, with a human label."""
        if self.humid_sensor:
            yield "humidity sensor", self.humid_sensor
        if self.temp_sensor:
            yield "temperature sensor", self.temp_sensor
        for i, switch in enumerate(self.switches):
            entity = switch.get("entity")
            if entity:
                yield "switch {}".format(i), entity

    def _apply_state(self, entity, state, switch_index, reason):
        """Apply state to switch and log the action.

        This used to read the current state, compare it to the target, and --
        when they differed -- call turn_on/turn_off and log "Turned ON/OFF" at
        INFO unconditionally. For an entity that does not exist `get_state`
        returns `None`, and `None == "off"` is False, so a missing switch fell
        straight through to a service call into nothing and a log line claiming
        it had worked.

        That is the same defect as T-52's false success line: a log asserting an
        outcome it never established. A command is only reported as sent when
        there was something to send it to.
        """
        try:
            # Check current state before making changes
            current_state = self.get_state(entity)

            if current_state is None:
                self.log(
                    "[HT004] Switch {}: {} does not exist -- not commanding it "
                    "{} ({})".format(switch_index, entity, state, reason),
                    level="ERROR",
                )
                return

            if current_state == state:
                return  # Already in desired state, no change needed

            unreachable = ha_states.not_reporting(current_state)
            if unreachable:
                # Still attempt it: an entity can report `unavailable` briefly
                # and still accept the command, and refusing outright would be a
                # behaviour change this ticket has no evidence for. What changes
                # is that the outcome is no longer reported as a success.
                self.log(
                    "[HT005] Switch {}: {} is {} -- commanding it {} anyway, "
                    "but it may not land ({})".format(
                        switch_index, entity, current_state, state, reason
                    ),
                    level="WARNING",
                )

            if state == "off":
                self.turn_off(entity)
                if not unreachable:
                    self.log(f"Switch {switch_index}: Turned OFF {entity} ({reason})", level="INFO")
            elif state == "on":
                self.turn_on(entity)
                if not unreachable:
                    self.log(f"Switch {switch_index}: Turned ON {entity} ({reason})", level="INFO")
            else:
                self.log(f"Switch {switch_index}: Unknown state '{state}' for {entity}", level="WARNING")
        except Exception as e:
            self.log(f"Error applying state '{state}' to {entity}: {str(e)}", level="ERROR")
            self.log(f"Traceback: {traceback.format_exc()}", level="ERROR")

