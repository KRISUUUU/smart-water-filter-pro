# Physical Hardware & ESPHome Specification

The ESP32 Ultra-Flow Sentinel Node hardware tier relies on an ESP32 microcontroller reading pulses from a YF-S201 Hall-effect flow sensor, computing flow volume, and pushing updates locally to Home Assistant Core.

---

## 1. Hardware Pinout & Wiring Diagram

The YF-S201 Hall-effect flow sensor requires $5\text{V}$ power to operate reliably. Because the ESP32 GPIO pins operate at a $3.3\text{V}$ logic level, the data line needs a pull-up resistor to pull the sensor output high to prevent floating logic states, while protecting the input pin.

### ESP32 and YF-S201 Connection Diagram

```text
                  ESP32 Microcontroller
                  +-----------------------+
                  |  [ ] 3V3         GND [ ]|---------+
                  |  [ ] EN          G23 [ ]|         |
                  |  [ ] SENSOR_VP   G22 [ ]|         |
                  |  [ ] SENSOR_VN   TX0 [ ]|         |
                  |  [ ] G34         RX0 [ ]|         |
                  |  [ ] G35         G21 [ ]|         |
                  |  [ ] G32         G19 [ ]|         |
                  |  [ ] G33         G18 [ ]|         |
                  |  [ ] G25         G5  [ ]|         |
                  |  [ ] G26         G17 [ ]|         |
     +------------|  [*] G27 (Data)  G16 [ ]|         |
     |            |  [ ] G14         G4  [ ]|         |
     |            |  [ ] G12         G0  [ ]|         |
     |            |  [ ] GND         G2  [ ]|         |
     |            +-----------------------+         |
     |                                              |
     |               +-----------------+            |
     +--[ 4.7kΩ ]----| YF-S201 Sensor  |            |
     |  Pull-up      |                 |            |
     |  Resistor     | (Yellow) Data   |            |
     |               | (Red) 5V VCC    |------------|--+ (5V VCC Power)
     |               | (Black) GND     |------------+
     |               +-----------------+
     +----------------------(Data Pin)
```

### Pull-Up Resistor Detail
A **$4.7\text{ kΩ}$ pull-up resistor** is connected between the **$5\text{V}$ VCC line** and the **Yellow Data Line**. When the internal Hall-effect sensor wheel rotates, it pulses the yellow data line low. When the Hall-effect transistor closes, the $4.7\text{ kΩ}$ resistor pulls the GPIO27 input back up to the high voltage level. 

The ESP32 pin is configured as `INPUT_PULLUP` to enable the internal high-resistance pull-ups, which work in parallel with the external $4.7\text{ kΩ}$ resistor to provide noise rejection and sharp logic edge transitions.

---

## 2. ESPHome `pulse_counter` Configuration

The flow sensor counts rotations of the turbine. The relationship between pulses and volume is determined by the sensor flow coefficient:
- **YF-S201 Constant**: Approximately $450\text{ pulses}$ per Liter.
- **Conversion Math**: The ESPHome `pulse_counter` platform measures counts per minute. To convert pulses per minute to Liters per minute:
  \[ \text{Flow Rate (L/min)} = \frac{\text{Pulses / Minute}}{450.0} = \text{Pulses / Minute} \times 0.133333 \]

### Debounce Filter Configuration
To eliminate fake pulses caused by electric noise or water hammer ripples, an internal filter is configured:
- **`internal_filter: 13us`**: Any pulse with a duration shorter than $13\text{ microseconds}$ is discarded directly by the ESP32 hardware pulse counter register.

### YAML Specification Snippet

```yaml
sensor:
  - platform: pulse_counter
    pin:
      number: GPIO27
      mode:
        input: true
        pullup: true
    name: "Water Flow Rate"
    id: water_flow_rate
    update_interval: 1s
    unit_of_measurement: "L/min"
    accuracy_decimals: 2
    internal_filter: 13us
    count_mode:
      rising_edge: INCREMENT
      falling_edge: DISABLE
    filters:
      - multiply: 0.133333
      - throttle: 2s
```

---

## 3. Riemann Sum Totalizer & Flash Persistence

Calculating the total volume directly on the ESP32 CPU registers prevents data loss when Home Assistant is offline, rebooting, or experiencing network connectivity drops.

### Mathematical Riemann Sum
The ESP32 calculates cumulative water consumption by running a Riemann Sum on its internal clock. For each sensor reading interval $dt$ where flow rate $Q(t) > 0$:

\[ V_{total} = \sum_{t} Q(t) \cdot dt \]

Because the flow rate is measured in L/min, and the `on_raw_value` trigger fires with the current L/min value, the delta added to the total volume is:

\[ \Delta V = \frac{Q_{L/min}}{60.0} \]

This calculation runs in a high-priority loop directly on the ESP32 CPU:

```cpp
if (x > 0) {
  float current_flow = x * 0.133333;
  id(total_water_liters) += current_flow / 60.0;
}
```

### State Survivability & Flash Write Wear Protection
The accumulated volume is stored in the ESP32 global variable `total_water_liters`, configured with `restore_value: yes`.

- **NVRAM Restore**: The value is periodically written to the ESP32's non-volatile flash memory. Upon hardware power cycle, the boot bootloader restores the last saved state.
- **Wear Protection**: Flash memory degrades after excessive write cycles. To protect the flash chips:
  - **`flash_write_interval: 5min`**: Global states are only saved to flash memory once every 5 minutes. This reduces write wear by several orders of magnitude compared to writing on every pulse, while ensuring that at most 5 minutes of consumption data is lost during sudden hardware power outages.
