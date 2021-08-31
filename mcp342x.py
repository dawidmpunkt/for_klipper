# MCP342x external ADC Module for Klipper
# External ADC connected via I2C
# Date: 31.08.2021 - Dawid Murawski, dawid.m@gmx.net
#
# Compatible ADCs:
#       MCP3421 - MCP3428
#       ADS1013 - ADS1015
#       Tested MCP3421 on Linux MCU
#       Tested ADS1015 on Linux MCU
#############################################################

#add to printer.cfg
#[mcp342x external_adc_name]
#Standard Adresses:
# MCP3421: 104 (0x68 in hex)
# ADS1015: 104 (0x68 in hex)
#i2c_address: 104
#currently, only rpi works as mcu
#i2c_mcu: rpi
#   The i2c address that the chip is using on the i2c bus. This
#   parameter must be provided.
#i2c_bus: i2c.1
#sensor_ID: e.g. ADS1015
##(Optional config: see device manual)
#resolution: 12 (default)
#gain: 1 (default)
#channel: 1 (default)

# Typing MCP_READ into Terminal returns a single voltage reading
## Optional input: MCP_READ CHANNEL= GAIN= RATE= RESOLUTION=
#  Query_ADC NAME="MCP_34XX" returns a single voltage reading
#  The Gcode Macro below returns a single voltage and time reading
##[gcode_macro QUERY_MCP34]
## gcode:
##     {% set sensor = printer["mcp342x external_adc_name"] %}
##     {action_respond_info(
##         "Voltage: %.2f C\n"
##         "Time: %.2f%%" % (
##            sensor.voltage,
##            sensor.time))}

# further TODOs: test I2C via mcu; create virtual output pin

## ADS10XX: ##
# Second Byte: Address pointer
# 0 0 0 0 0 0 P1 P2
#             0  0: Conversion register
#             0  1: Config register
#             1  0: Lo_threshold
#             1  1: Hi_threshold

# Config register
# 0  0  0  0  0  0  0  0
# 15 14 13 12 11 10 9  8
# OS [  MUX ] [ PGA  ] Mode
# ----------------------
# 0  0  0  0  0  0  0  0
# 7  6  5  4  3  2  1  0
# [  DR ] CM  CP CL [CQ]
#
# OS: Operational Status (write 1 for single shot)
# MUX:                  000: AIN0+AIN1 (def)
# Input Multiplexer     001: AIN0+AIN3
# (ADS1015 only)        010: AIN1+AIN3
#                       011: AIN2+AIN3
#                       100: AIN0+GND
#                       101: AIN1+GND
#                       110: AIN2+GND
#                       111: AIN3+GND
# PGA:                  000: FSR = +- 6.144 V (Gain 0.25)
# No function on        001: FSR = +- 4.096 V (Gain 0.5)
# ADS1013               010: FSR = +- 2.048 V (def)
#                       011: FSR = +- 1.024 V (Gain 2)
#                       100: FSR = +- 0.512 V (Gain 4)
#                       101: FSR = +- 0.256 V (Gain 8)
#                       110: FSR = +- 0.256 V
#                       111: FSR = +- 0.256 V
# Mode:                 0: continuous conversion
#                       1: single shot
# DR:                    000: 128 SPS
# Data rate             001: 250 SPS
#                       010: 490 SPS
#                       011: 920 SPS
#                       100: 1600 SPS (def)
#                       101: 2400 SPS
#                       110: 3300 SPS
#                       111: 3300 SPS
## MCP34XX: ##
# Write command for one shot reading is 10001000. 
# The hex value is 0x88.
# 7th bit: 1 (start new conversion)
# 6+5th bit: 00 (address bit, not used in mcp3425)
# 4th bit: 0 (one shot mode)
# 3rd+2nd bit: 10 (sample rate 15 ms, 16 bit)
# 1st+0th bit: gain selection: 00 (gain = 1)


from . import bus
import pins
import mcu
import logging

SUPP_DEV_18 = ['MCP3421', 'MCP3422', 'MCP3423', 'MCP3424']
SUPP_DEV_16 = ['MCP3425', 'MCP3426', 'MCP3427', 'MCP3428']
SUPP_DEV_12 = ['ADS1013', 'ADS1014', 'ADS1015']

VREF = 2.048

N_CHANNELS = {
    'MCP3421': 1,
    'MCP3422': 2,
    'MCP3423': 3,
    'MCP3424': 4,
    'MCP3425': 1,
    'MCP3426': 2,
    'MCP3427': 3,
    'MCP3428': 4,
    'ADS1013': 1,
    'ADS1014': 1,
    'ADS1015': 8,
}

# ADS1013 does not have PGA
ADS_GAIN = {
    0.25: 0,
    0.5: 1,
    1: 2,
    2: 3,
    4: 4,
    8: 5
}

MCP_GAIN = {
    1: 0,
    2: 1,
    4: 2,
    8: 3
}

MCP_RATE = {
    240: (12,0),
    60: (14,1),
    15: (16,2),
    3.75: (18,3)
}

MCP_RES = {
    12: (240,0),
    14: (60,1),
    16: (15,2),
    18: (3.75,3)
}

MCP_CHANNEL = {
    1: 0b00000000,
    2: 0b00100000,
    3: 0b01000000,
    4: 0b01100000
}

ADS_RATE = {
    128: 0,
    250: 1,
    490: 2,
    920: 3,
    1600: 4,
    2400: 5,
    3300: 6,
    3300: 7
}

class mcp342x:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]
        self.reactor = self.printer.get_reactor()
        self.i2c = bus.MCU_I2C_from_config(config,
                            default_speed=100000)
        self.deviceId = config.get('sensor_ID').upper()
        self.devicePrefix = self.deviceId[0:3]
        self.resolution = config.getint('resolution',12)
        # Check if device is supported
        if self.deviceId not in (SUPP_DEV_16 and \
                SUPP_DEV_18 and SUPP_DEV_12):
            raise config.error(self.deviceId + " not supported")
        # Set channel
        self.channel = config.getint('channel',minval=1,
                            maxval=N_CHANNELS[self.deviceId],
                            default=1)-1
        # Check if selected resolution is correct/supported
        if self.resolution not in [12, 14, 16, 18]:
            raise config.error("Invalid resolution")
        elif self.resolution == 18 and \
                self.deviceId not in SUPP_DEV_18:
            raise config.error("18 bit sampling not supported by " +
                            self.deviceId)
        elif self.resolution != 12 and \
                self.deviceId in SUPP_DEV_12:
            raise config.error(self.deviceId + 
                " only supports 12 bit sampling")
        self.gain = config.get('gain',1)
        if self.gain not in eval(self.devicePrefix + "_GAIN"):
            raise config.error("Invalid PGA setting")
        self.printer.register_event_handler("klippy:connect",
                                            self.handle_connect)
        self.gcode = self.printer.lookup_object('gcode')
        # Define reference value
        self.LSB = (VREF*2)/(2**self.resolution)
        #Register gcode command
        self.gcode.register_command('MCP_READ', self.cmd_mcp_read)
        # Register ADC
        query_adc = config.get_printer().load_object(config, 'query_adc')
        query_adc.register_adc("MCP_34XX", self)

    def get_status(self, eventtime):
        last_value = self.sample_voltage(self.channel, 
        self.gain, self.resolution, 1600)
        return {
            'voltage': float(last_value[0]),
            'time': float(last_value[1])
        }

    def sample_voltage(self, channel, gain, resolution, rate):
        _gain = eval(self.devicePrefix + "_GAIN")[gain]
        _rate = eval(self.devicePrefix + "_RATE")[rate]
        # Setup ADC
        if self.devicePrefix == "MCP":
            _rate = MCP_RES[resolution]
            conf = 0b10000000 | channel << 5 | _rate[1] << 2 | _gain
        else:
            _conf1 = 0b10000001 | channel << 4 | _gain << 1
            _conf2 = 0b00000011 | _rate << 5
            conf = [0b00000001, _conf1, _conf2]
        LSB = (VREF*2)/(2**resolution)
        # Write ADC Configuration
        self.i2c.i2c_write(bytearray(conf))
        # Wait for conversion end
        self.reactor.pause(self.reactor.monotonic() + (1.05 / int(rate)))
        # Read 3 bytes of data
        params = self.i2c.i2c_read([0b00000000], 3)
        response = bytearray(params['response'])
        #Calculate response according to
        ##12, 14, 16 or 18 bit resolution
        _value = response[0] << (resolution - 8)
        if self.devicePrefix == 'MCP':
            #Cut repeating leading bits
            _value &= bin(2 ** resolution - 1)
        value = float(_value)
        # Check sign
        if value > ( 2 **(resolution-1) - 1):
            value -= (2**resolution)
        # calculate Voltage
        rVolt = value * LSB / gain
        rTime = params['#receive_time']
        return rVolt, rTime

    def get_last_value(self):
        last_value = self.sample_voltage(self.channel,
            self.gain, self.resolution, 1600)
        return float(last_value[0]), float(last_value[1])

    def get_channel(self, channel):
        last_value = self.sample_voltage(channel,
            self.gain, self.resolution, 1600)
        return float(last_value[0])

    def handle_connect(self):
        logging.info("mcp_connect")

#Single reading
    def cmd_mcp_read(self, gcmd):
        channel = int(gcmd.get('CHANNEL', self.channel)) - 1
        gain = float(gcmd.get('GAIN',self.gain))
        resolution = float(gcmd.get('RESOLUTION',self.resolution))
        # Setup ADC
        if self.devicePrefix == "MCP":
            try:
                rate = int(gcmd.get('RATE'))
                resolution = _rate[0]
            except:
                _rate = MCP_RES[resolution]
        else:
            rate = int(gcmd.get('RATE', 1600))
        rValue = self.sample_voltage(channel, gain, resolution, rate)
        Volt = rValue[0]
        Time = rValue[1]
        gcmd.respond_info('Channel {} Voltage: {} V, Time: {}'.format(channel + 1, Volt, Time))

def load_config_prefix(config):
    return mcp342x(config)
