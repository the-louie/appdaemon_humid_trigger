import time
import json
import appdaemon.plugins.hass.hassapi as hass

#HumidTrigger:
#  module: i1_humid_trigger
#  class: HumidTrigger 
#  sensors:
#    humidity: "sensor.v2_hall_minivind_humid" 
#    temperature: "sensor.v2_hall_minivind_temp"
#  switches:
#    - entity: "switch.v2_minivind"
#      min_temp: 10
#      lt: 
#        state: "off"
#        value: 45
#      gt: 
#        state: "on"
#        value: 50
#

class HumidTrigger(hass.Hass):
  def initialize(self):
    self.log("Loading HumidTrigger()")

    self.humid_sensor = self.args.get("sensors", {}).get("humidity")
    self.temp_sensor = self.args.get("sensors", {}).get("temperature")
    self.switches = self.args.get("switches")

    if self.humid_sensor is None or self.temp_sensor is None:
      self.log(" >> HumidTrigger.initialize(): Warning - Not configured")
      return
    if not isinstance(self.switches, list):
      self.light = [self.switches]

    self.listen_state(self.state_change_humid, self.humid_sensor)
    
    self.log(" >> HumidTrigger {} {} ==> {}".format(self.humid_sensor, self.temp_sensor,
                                                 self.switches))
    self.check_state(self.get_state(self.humid_sensor), self.get_state(self.temp_sensor))

  def state_change_humid(self, entity, attribute, old_humid, new_humid, kwargs):
    if new_humid == old_humid or new_humid is None:
      return
    new_temp = self.get_state(self.temp_sensor) 
    if new_temp is None:
      return

    self.check_state(new_humid, new_temp)

  def state_change_temp(self, entity, attribute, old_temp, new_temp, kwargs):
    if new_temp == old_temp or new_temp is None:
      return
    new_humid = self.get_state(self.humid_sensor)
    if new_humid is None:
      return
    self.check_state(new_humid, new_temp)


  def check_state(self, humid, temp):
    if humid is None or humid == 'unavailable':
        return
    if temp is None or temp == 'unavailable':
        return
    self.log("check_state({}, {})".format(humid, temp))
    for switch in self.switches:
      lt_value = switch.get('lt', {}).get('value')
      gt_value = switch.get('gt', {}).get('value')
      lt_state = switch.get('lt', {}).get('state')
      gt_state = switch.get('gt', {}).get('state')
      entity = switch.get('entity')
      min_temp = switch.get('min_temp')

      if float(temp) < min_temp:
          self.log("Too cold {} < {}".format(temp, min_temp))
          continue

      if not lt_value or not gt_value or not lt_state or not gt_state or not entity:
          self.log('skipping due to missing values: {}'.format(switch))
          continue

      if float(humid) < float(lt_value):
        self.log('check_state({}) >>> lt: {} state: {}'.format(humid, lt_value, lt_state))
        new_state = lt_state
      elif float(humid) > float(gt_value):
        self.log('check_state({}) >>> gt: {} state: {}'.format(humid, gt_value, gt_state))
        new_state = gt_state
      else:
        self.log('check_state({}) >>> no change'.format(humid))
        new_state = None

      if new_state == "off":
        self.turn_off(entity)
      elif new_state == "on":
        self.turn_on(entity)

