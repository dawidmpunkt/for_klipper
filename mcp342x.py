# MCP342x external ADC Module for Klipper
# External ADC connected via I2C
#
# Compatible Sensors:
#       MCP3421 - Untested
#       MCP3422 - Untested
#       MCP3423 - Untested
#       MCP3424 - Untested
#       MCP3425 - Tested on Linux MCU.
#       MCP3428 - Untested
#
#############################################################

#add to printer.cfg
#[mcp342x external_adc_name]
#Standard Adress is 0x68 (104 in digital)
#i2c_address: 104
#currently, only rpi works as mcu
#i2c_mcu: rpi
#   The i2c address that the chip is using on the i2c bus. This
#   parameter must be provided.
#i2c_bus: i2c.1
#sensor_type: 

#Typing MCP_READ into Terminal returns a single voltage reading
# -> next TODO: create virtual output pin
# -> further TODOs: add options for other mcp342x than mcp3425; 
# add options to select gain, resolution, channels etc.; 
# test I2C via mcu; 

from . import bus
import logging

MCP_RESOLUTIONS = {
    8:  0b00000000,
    12: 0b00000100,
    16: 0b00001000,
    18: 0b00001100
}


class mcp342x:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]
        self.reactor = self.printer.get_reactor()
        self.i2c = bus.MCU_I2C_from_config(config, 
                                           default_speed=100000)
        self.deviceId = config.get('sensor_type')
        self.resolution = config.get('resolution',16)
        if self.resolution not in MCP_RESOLUTIONS:
            raise config.error("Invalid MCP342x resolution.)
        elif resolution == 18 and \
                self.deviceId in ("MCP3425", "MCP3426", "MCP3427"):
            raise config.error("18 bit sampling not supported by" +
                            self.device)
        self.printer.register_event_handler("klippy:connect",
                                            self.handle_connect)
        self.gcode = self.printer.lookup_object('gcode')
        #Register gcode command
        self.gcode.register_command('MCP_READ', self.cmd_mcp_read)

    def handle_connect(self):
        logging.info("mcp_connect")
        
    #Single reading
    def cmd_mcp_read(self, gcmd):
        # Write command for one shot reading is 10001000. 
        # The hex value is 0x88.
        # 7th bit: 1 (start new conversion)
        # 6+5th bit: 00 (address bit, not used in mcp3425)
        # 4th bit: 0 (one shot mode)
        # 3rd+2nd bit: 10 (sample rate 15 ms, 16 bit)
        # 1st+0th bit: gain selection: 00 (gain = 1)
        self.i2c.i2c_write([0x88])
        #write_command = hex()
        #self.i2c.i2c_write([write_command])

        # Wait 15ms
        self.reactor.pause(self.reactor.monotonic() + .15)
        # Read 3 bytes of data
        params = self.i2c.i2c_read([], 2)
        response = bytearray(params['response'])
        value = float((response[0] << 8) + response[1])
        bit = 16 # 16 bit resolution
        gain = 1
        Vref = 2.048
        # Check sign
        if value > ( 2 **(bit-1) - 1):
            value -= (2**bit)         
        # calculate Voltage
        # LSB: 62.5 mV in 16 bit resolution
        LSB = (Vref*2)/(2**bit) 
        rVolt = float(value) * LSB / gain
        
        # Dump response into Terminal
        gcmd.respond_info('I2C Response: {} '.format(rVolt))


def load_config_prefix(config):
    return mcp342x(config)
