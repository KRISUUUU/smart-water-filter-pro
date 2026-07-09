substitutions:
  pulses_per_liter: "450"
  flow_multiplier: "0.133333"

esphome:
  name: smart-water-filter-pro
  friendly_name: Smart Water Filter PRO

esp32:
  variant: esp32
  framework:
    type: esp-idf
    advanced:
      minimum_chip_revision: "3.1"
      sram1_as_iram: true


logger:


api:
  encryption:
    key: !secret api_key


ota:
  - platform: esphome
    password: !secret smart_water_filter_pro__ota_password


wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password

  fast_connect: true

  manual_ip:
    static_ip: 10.0.50.95
    gateway: 10.0.50.1
    subnet: 255.255.255.0
    dns1: 10.10.10.10
    dns2: 10.10.10.11


captive_portal:


time:
  - platform: homeassistant
    id: ha_time
    timezone: Europe/Warsaw


preferences:
  flash_write_interval: 5min


globals:

  - id: total_water_liters
    type: double
    restore_value: yes
    initial_value: "0.0"

  - id: max_flow_rate
    type: float
    restore_value: yes
    initial_value: "0.0"


#
# STATUS
#

binary_sensor:

  - platform: status
    name: "ESP Online"


#
# TEXT SENSORS
#

text_sensor:

  - platform: version
    name: "ESPHome Version"


  - platform: template
    id: water_last_flow_timestamp
    name: "Water Last Flow Timestamp"
    icon: mdi:clock-outline



#
# BASIC ESP DIAGNOSTICS
#

sensor:

  - platform: uptime
    name: "Uptime"
    update_interval: 60s


  - platform: wifi_signal
    name: "WiFi RSSI"
    update_interval: 60s



#
# MAIN YF-S201 FLOW SENSOR
#

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

      # YF-S201:
      # ~450 pulses = 1 liter
      # pulse_counter daje pulses/min
      # L/min = pulses/min / 450

      - multiply: ${flow_multiplier}


      - throttle: 2s



    on_raw_value:

      then:

        - lambda: |-

            if (x > 0) {


              float current_flow = x * atof("${flow_multiplier}");


              //
              // MAX FLOW
              //

              if (current_flow > id(max_flow_rate)) {

                id(max_flow_rate) = current_flow;

              }



              //
              // TOTAL LITERS
              //

              id(total_water_liters) +=
                current_flow / 60.0;



              //
              // LAST FLOW TIME
              //

              auto now = id(ha_time).now();


              if (now.is_valid()) {

                id(water_last_flow_timestamp)
                  ->publish_state(
                    now.strftime("%Y-%m-%d %H:%M:%S")
                  );

              }

            }



#
# MAX FLOW SENSOR
#

  - platform: template

    name: "Water Max Flow Rate"

    id: water_max_flow_rate


    unit_of_measurement: "L/min"

    accuracy_decimals: 2


    icon: mdi:gauge-max


    lambda: |-

      return id(max_flow_rate);


    update_interval: 5s




#
# TOTAL WATER
# HA integration uses this
#

  - platform: template

    name: "Water Total Volume"

    id: water_total_volume


    unit_of_measurement: "L"


    accuracy_decimals: 3


    device_class: water

    state_class: total_increasing



    lambda: |-

      return id(total_water_liters);



    update_interval: 10s
