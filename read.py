#!/usr/bin/python -u
import time
from influxdb import InfluxDBClient
import logging
import math
import os
import re
import argparse
import os.path
import smbus
def writePidFile():
        pid = str(os.getpid())
        currentFile = open("/var/run/myreader.pid", "w")
        currentFile.write(pid)
        currentFile.close()

writePidFile()
logging.basicConfig(filename='/var/log/example.log',level=logging.DEBUG)
logging.debug('This message should go to the log file')
logging.info('So should this')
logging.warning('And this, too')
# Global data
# I2C bus (1 at newer Raspberry Pi, older models use 0)
bus = smbus.SMBus(1)
# I2C address of HMC5883
address = 0x1e

# Trigger level and hysteresis

trigger_level = 400
trigger_hyst = 10
# Amount to increase the counter at each trigger event
trigger_step = 0.01



# Read block data from HMC5883
def read_data():
  return bus.read_i2c_block_data(address, 0x00)

# Convert val to signed value
def twos_complement(val, len):
  if (val & (1 << len - 1)):
    val = val - (1<<len)
  return val

# Convert two bytes from data starting at offset to signed word
def convert_sw(data, offset):
  return twos_complement(data[offset] << 8 | data[offset+1], 16)

# Write one byte to HMC5883
def write_byte(adr, value):
  bus.write_byte_data(address, adr, value)
  
def read_counter():
  if os.path.exists("counter"):
    f = open("counter","r") #opens file with name of "test.txt"
    val = float(f.read())
    f.close()
    return val
  else:
    return 0

def write_counter(val,file):
   f = open(file,"w")
   f.write(val)
   f.close()

def write_value(val,file):
   f = open(file, "a")
   f.write(val +"\n")
   f.close()
# Main
client = InfluxDBClient(host="localhost", port=8086, database="homematic")
retention_policy="mypolicy100"
#client.create_retention_policy(retention_policy, '100d', 0, default=True)

def write_db(counter, bx, by, bz):
  cur_time =  int(time.time()*1000)
  json_body = [
        {
            "measurement": "gasmeter",
            "tags": {
                "type": "counter",
                "measure": "ccm"
            },
            "fields": {
                "counter": counter,
                "bx": bx,
                "by": by,
                "bz": bz
            }
        }
    ]
  client.write_points(json_body)
  logging.info("write:"+str(json_body))
  
def main():

  # Init HMC5883
  write_byte(0, 0b01110000) # Rate: 8 samples @ 15Hz
  write_byte(1, 0b11100000) # Sensor field range: 8.1 Ga
  write_byte(2, 0b00000000) # Mode: Continuous sampling

  trigger_state = 0
  timestamp = time.time()
  counter = read_counter()
  print "restoring counter to %f" % counter
  while(1==1):
    # read data from HMC5883
    data = read_data()

    # get x,y,z values of magnetic induction
    bx = convert_sw(data, 3) # x
    by = convert_sw(data, 7) # y
    bz = convert_sw(data, 5) # z

    # compute the scalar magnetic induction
    # and check against the trigger level
    old_state = trigger_state
    b = math.sqrt(float(bx*bx) + float(by*by) + float(bz*bz))
    print ("Value: " + str(b))
    if b > trigger_level + trigger_hyst:
      trigger_state = 1
    elif b < trigger_level - trigger_hyst:
      trigger_state = 0
    if old_state == 0 and trigger_state == 1:
      # trigger active -> update count rrd
      counter += trigger_step
      update = "N:%f:%f" % (counter, trigger_step)
      timestamp = time.time()
      write_db(counter,bx,by,bz)
    elif time.time() - timestamp > 3600:
      # at least on update every hour
      update = "N:%f:%f" % (counter, 0)
      timestamp = time.time()
      write_db(counter,bx,by,bz)
    print (counter)
  #  write_db(counter,bx,by,bz)
    print (counter)
    write_value(str(b),"values")
    write_counter(str(counter),"counter")
    time.sleep(2)


if __name__ == '__main__':
  main()

