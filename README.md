# HumidTrigger AppDaemon App

An AppDaemon app for Home Assistant that automatically controls switches based on humidity and temperature conditions.

## Features

- **Humidity-based control**: Automatically turn switches on/off based on humidity thresholds
- **Temperature protection**: Prevent operation below a minimum temperature to avoid freezing
- **Multiple switches**: Control multiple switches with different configurations
- **Sane defaults**: Minimal configuration required with sensible defaults
- **Extensive logging**: Comprehensive logging for debugging and monitoring

## Configuration

### Basic Configuration

```yaml
HumidTrigger:
  module: i1_humid_trigger
  class: HumidTrigger
  sensors:
    humidity: "sensor.room_humid"
    temperature: "sensor.room_temp"
  switches:
    - entity: "switch.room_switch"
```

### Advanced Configuration

```yaml
HumidTrigger:
  module: i1_humid_trigger
  class: HumidTrigger
  sensors:
    humidity: "sensor.room_humid"
    temperature: "sensor.room_temp"
  switches:
    - entity: "switch.room_switch"
      min_temp: 10  # Minimum temperature in °C
      lt:
        state: "off"  # State when humidity is low
        value: 55     # Humidity threshold in %
      gt:
        state: "on"   # State when humidity is high
        value: 60     # Humidity threshold in %
```

## Default Values

The app provides sensible defaults to minimize configuration:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_temp` | 5°C | Minimum temperature to prevent freezing |
| `lt.value` | 45% | Turn off when humidity drops below this |
| `lt.state` | "off" | State to apply when humidity is low |
| `gt.value` | 60% | Turn on when humidity rises above this |
| `gt.state` | "on" | State to apply when humidity is high |

## How It Works

1. **Monitoring**: The app continuously monitors humidity and temperature sensors
2. **Temperature Check**: If temperature is below `min_temp`, switches are not operated
3. **Humidity Control**:
   - If humidity < `lt.value`: Apply `lt.state`
   - If humidity > `gt.value`: Apply `gt.state`
   - If humidity is between thresholds: No change
4. **Logging**: All actions are logged with detailed context

## Installation

1. Copy `i1_humid_trigger.py` to your AppDaemon apps directory
2. Copy `config.yaml.example` to your AppDaemon configuration
3. Modify the configuration to match your sensors and switches
4. Restart AppDaemon

## License

Copyright (c) 2024 the_louie

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
