/* paintbrush.pde - Reads in commands over serial
 * by Nirav Patel <nrp@eclecti.cc>
 *
 * Uses the skeleton of the MinimalInkShieldLite.pde sketch with this license:
 *
 *  MinimalInkShieldLite.pde - Basic InkShield sketch (for Arduino and Arduino Mega)
 *  Copyright 2011, Nicholas C Lewis, GNU Lesser General Public License
 *  http://nicholasclewis.com/inkshield/
 *
 *  This library is free software; you can redistribute it and/or
 *  modify it under the terms of the GNU Lesser General Public
 *  License as published by the Free Software Foundation; either
 *  version 2.1 of the License, or (at your option) any later version.
 *  http://www.gnu.org/licenses/lgpl-2.1.html
 * 
 *  This library is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 *  Lesser General Public License for more details.
 * 
 *  You should have received a copy of the GNU Lesser General Public
 *  License along with this library; if not, write to the Free Software
 *  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
 */

//this library will work with both Arduino and Arduino Mega
#include <InkShieldLite.h>

//initialize shield on pin 2
const byte pulsePin = 2;
// precalculate patterns for different levels of saturation
const uint32_t grayscale[5] = {0, 0x08080808, 0x88888888, 0xAAAAAAAA, 0xFFFFFFFF};
uint8_t index = 0;
uint8_t command[6];
uint8_t command_index = 0;
uint8_t nozzles[12];

void setup()
{
  setABCDPinMode(abcdA0A3, OUTPUT);  //set the abcd pins as outputs
  pinMode(pulsePin, OUTPUT);         //set the pulse pin as output
  Serial.begin(115200);
}

void loop()
{
    while (Serial.available())
        update_command(Serial.read());
    index++;
    word pulse = calculate_pulse();
    spray_ink(pulse);
}

// pull in the new nozzle pattens from serial
void update_command(int incoming)
{
    // two high bits indicates the first byte in the range of 6
    if ((incoming & 0xC0) == 0xC0)
        command_index = 0;
    // the commands are 3 bits for each nozzle, a 0-6 index into the grayscale array
    nozzles[command_index*2] = (incoming & 0x38) >> 3;
    nozzles[command_index*2 + 1] = (incoming & 0x07);
    command_index++;
    // wrap around defensively to avoid memory corruption
    if (command_index > 5) command_index = 0;
}

// each 800us timestep, calculate the pulse pattern to use
word calculate_pulse()
{
    word ret = 0;
    for (uint8_t i = 0; i < 12; i++) {
        ret |= (((grayscale[nozzles[i]] >> (index % 32)) & 1) << i);
    }
    return ret;
}

void spray_ink(word strip)
{
  //loop thru the strip
  for(byte i = 0; i <= 11; i++){
    if(strip & 1<<i){
      fastABCDDigitalWrite(abcdA0A3, i, HIGH);  //set abcd (nozzle address)
      fastDigitalWrite(pulsePin, HIGH); delayMicroseconds(5);  //pulse pin high, wait 5us
      fastDigitalWrite(pulsePin, LOW); //pulse pin low
      fastABCDDigitalWrite(abcdA0A3, i, LOW); //reset abcd
    }
  }	
  //wait to be sure we don't try to fire nozzles too fast and burn them out
  delayMicroseconds(800);
}
