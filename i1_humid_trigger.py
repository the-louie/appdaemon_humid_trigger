import time
import json
import appdaemon.plugins.hass.hassapi as hass

#HumidTrigger:
#  module: i1_humid_trigger
#  class: HumidTrigger 
#  switches:
#    - entity: "switch.minivind_flakt"
#      lt: 
#        state: "off"
#        value: 38
#      gt: 
#        state: "on"
#        value: 40
#  entity: "sensor.v2_hall_minivind_humid" 
#

class HumidTrigger(hass.Hass):
  def initialize(self):
    self.log("Loading HumidTrigger()")

    self.entity = self.args.get("entity")
    self.switches = self.args.get("switches")

    if self.entity is None:
      self.log(" >> HumidTrigger.initialize(): Warning - Not configured")
      return
    if not isinstance(self.switches, list):
      self.light = [self.switches]

    self.listen_state(self.state_change, self.entity)
    
    self.log(" >> HumidTrigger {} ==> {}".format(self.entity,
                                                 self.switches))
    self.check_state(self.get_state(self.entity))

  def state_change(self, entity, attribute, old, new, kwargs):
    if new != old and new is not None:
      self.check_state(new)


  def check_state(self, new):
    if new is None:
        return
    #self.log("check_state({})".format(new))
    for switch in self.switches:
      lt_value = switch.get('lt', {}).get('value')
      gt_value = switch.get('gt', {}).get('value')
      lt_state = switch.get('lt', {}).get('state')
      gt_state = switch.get('gt', {}).get('state')
      entity = switch.get('entity')

      if not lt_value or not gt_value or not lt_state or not gt_state or not entity:
          self.log('skipping due to missing values: {}'.format(switch))
          continue

      if float(new) < float(lt_value):
        self.log('check_state({}) >>> lt: {} state: {}'.format(new, lt_value, lt_state))
        new_state = lt_state
      elif float(new) > float(gt_value):
        self.log('check_state({}) >>> gt: {} state: {}'.format(new, gt_value, gt_state))
        new_state = gt_state
      else:
        self.log('check_state({}) >>> no change'.format(new))
        new_state = None

      if new_state == "off":
        self.turn_off(entity)
      elif new_state == "on":
        self.turn_on(entity)

