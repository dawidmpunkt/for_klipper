# MCP342x external ADC Module for Klipper
# External ADC connected via I2C

# MCP3425 reference manual: 
# http://www.microchip.com/downloads/en/DeviceDoc/22072b.pdf

#add to printer.cfg
#[mcp342x external_adc_name]
#Standard Adress is 0x68 (104 in digital)
#i2c_address: 104
#currently, only rpi is possible as mcu
#i2c_mcu: rpi
#   The i2c address that the chip is using on the i2c bus. This
#   parameter must be provided.
#i2c_bus: i2c.1

#Currently working on reading data from the first channel
# -> Current goal: Typing MCP_STATUS into Terminal should return a single reading. Reading should be correct.

from . import bus
import logging

class mcp342x:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]
        self.reactor = self.printer.get_reactor()
        self.i2c = bus.MCU_I2C_from_config(config, default_speed=100000)
        self.printer.register_event_handler("klippy:connect",
                                            self.handle_connect)
        self.gcode = self.printer.lookup_object('gcode')
        #Register gcode command
        self.gcode.register_command('MCP_STATUS', self.cmd_mcp_status)

    def handle_connect(self):
        logging.info("mcp_connect")
        
    #Single reading
    def cmd_mcp_status(self, gcmd):
        # Write command for one shot reading is 10001000. The hex value is 0x80.
        # 7th bit: 1 (start new conversion)
        # 6+5th bit: 00 (address bit, not used in mcp3425)
        # 4th bit: 0 (one shot mode)
        # 3rd+2nd bit: 10 (sample rate 15 ms, 16 bit)
        # 1st+0th bit: gain selection: 00 (gain = 1)
        self.i2c.i2c_write([0x88])

        # Wait 15ms
        self.reactor.pause(self.reactor.monotonic() + .15)
        # Read 3 bytes of data
        params = self.i2c.i2c_read([], 3)
        # Dump response into Terminal
        gcmd.respond_info("I2C Response: " + str(params))

def load_config_prefix(config):
    return mcp342x(config)
