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
# -> Current goal: Typing MCP_STATUS into Terminal should return a single reading

from . import bus

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
        # Device Adress for MCP3425 is 0x68. binary: 1101000.  104 is the decimal value.
        # In my case, i2c_write only accepts decimal
        i2c_addr = self.i2c.get_i2c_address()
        # Command for single shot reading is 10001000. The decimal value is 136.
        # 8th bit: start conversion
        # 4th bit: sample rate 15 ms, 16 bit
        # single-shot, gain = 1,
        single_shot = 136
        self.i2c.i2c_write([i2c_addr, single_shot])

        # Wait 15ms
        self.reactor.pause(self.reactor.monotonic() + .15)
        # Write 0x00
        # Read 3 bytes of data
        params = self.i2c.i2c_read(0, 3)
        # Dump response into Terminal
        gcmd.respond_info("I2C Response: " + str(params))

def load_config_prefix(config):
    return mcp342x(config)
