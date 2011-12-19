""" Semi-Automatic Paintbrush 

Copyright (c) 2011, Nirav Patel <http://eclecti.cc>

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

Uses an infrared camera, an InkShield, and your arm to copy great works of art, 
or just any old picture.
"""

#!/usr/bin/env python

import sys
import math
import getopt
import numpy
from numpy import linalg
import serial
import pygame
from homography import *

class Paintbrush:
    def __init__(self, filename, serialport, canvas_inches):
        pygame.init()
        self.camera = IRCamera()
        if serialport == None:
            serialport = 0
        self.port = serial.Serial(serialport, 115200, timeout=200)
        self.display = pygame.display.set_mode((640, 480),0)
        self.clock = pygame.time.Clock()
        
        # size of the canvas in dots.  the cartridge is 96dpi
        self.canvas_size = (int(canvas_inches[0]*96), int(canvas_inches[1]*96))
        # scale and fit the image to the canvas size
        image = pygame.image.load(filename)
        image = self.convert_to_greyscale(image)
        image_rect = image.get_rect()
        canvas_rect = pygame.Rect((0, 0), self.canvas_size)
        image_rect = image_rect.fit(canvas_rect)
        image = pygame.transform.smoothscale(image, (image_rect.size))
        self.canvas = pygame.Surface(canvas_rect.size, 0, self.display)
        self.canvas.fill((255, 255, 255))
        self.canvas.blit(image, image_rect.topleft)
        
        self.transformer = PerspectiveTransform(self.canvas_size)
        self.transform = []
        self.nozzles = [0]*12
        self.point = None
        self.dx = 0.0
        self.painting = False
        
    # fast conversion from rgb to a desaturated greyscale image
    def convert_to_greyscale(self, image):
        array = pygame.surfarray.pixels3d(image)
        iarray = array.astype(numpy.int)
        # slicing hint from http://dmr.ath.cx/gfx/python/
        r = iarray[:, :, 0]
        g = iarray[:, :, 1]
        b = iarray[:, :, 2]
        # convert to greyscale by luminance
        gray = (30*r+59*g+11*b)/100
        gray = gray.astype(numpy.uint8)
        array[:, :, 0] = gray
        array[:, :, 1] = gray
        array[:, :, 2] = gray
        return image
        
    def update_display(self, image):
        self.display.blit(image, (0, 0))
        if self.point != None:
            pygame.draw.rect(self.display, (127, 255, 127), (self.point[0], self.point[1], 12, 12), 3)
        pygame.display.flip()
            
    def new_point(self):
        self.cal_point = self.transformer.generate_point()
        print "Calibrating, move the printer head to %s and press any key" % str(self.cal_point)
       
    def calibrate(self):
        # the perspective transform needs four points
        cam_point = self.camera.get_point()
        needs_points = self.transformer.add_point(self.cal_point, cam_point)
        if needs_points:
            self.new_point()
            return True
        else:
            self.transform = self.transformer.calculate()
            print "Done calibrating, press any key to start painting!"
            pygame.display.set_mode(self.canvas_size, 0)
            return False
    
    def update_location(self):
        c = self.camera.get_point()
        if c:
            # transform from the camera coordinates to canvas coordinates
            p = numpy.array([c[0], c[1], 1])
            p = numpy.dot(self.transform, p)
            new_point = (p[0]/p[2], p[1]/p[2])
            
            if self.canvas.get_rect().collidepoint(new_point):
                # calculate how fast the brush is moving
                if self.point:
                    self.dx = new_point[0]-self.point[0]
                else:
                    self.dx = 0.0
                self.point = new_point
            else:
                self.point = None
        else:
            self.point = None
        
    def calculate_brush(self):
        if self.dx < 0.0:
            return
        width = max(1,int(abs(self.dx)))
        
        x = int(self.point[0])
        
        # this is only useful if we are painting both left and right, currently disabled
        if self.dx < 0.0:
            x -= width
        
        if x < 0:
            width -= x
            x = 0
            
        window = pygame.Rect((x, int(self.point[1])), (width, 1))
        h = 12
        
        for i in range(0, 12):
            # calculate the average color on the path of each nozzle
            if window.bottom > self.canvas_size[1]:
                h = i + 1
                break
            
            color = pygame.transform.average_color(self.canvas, window)
            self.nozzles[i] = min(4,(255-color[0])/48)
            window.move_ip(0, 1)
        
        # clear the area we are painting so it isn't painted again in the future
        window.topleft = (x, int(self.point[1]))
        window.height = h
        self.canvas.fill((255, 255, 255), window)
        
    def send_command(self):
        # pack two 0-5 values in each byte, and give the first byte a 0xC0 header
        command = bytearray(6)
        command[0] = 0xC0
        for i in range(0, 6):
            command[i] |= self.nozzles[i*2] << 3
            command[i] |= self.nozzles[i*2+1]
        self.port.write(command)
    
    def run(self):
        going = True
        calibrating = True
        self.new_point()
        
        while going:
            cam_image = self.camera.update()
            if calibrating:
                self.update_display(cam_image)
            else:
                self.update_location()
                self.nozzles = [0]*12
                if self.painting and self.point != None:
                    self.calculate_brush()
                self.send_command()
                self.update_display(self.canvas)
            
            events = pygame.event.get()
            for e in events:
                if e.type == QUIT or (e.type == KEYDOWN and e.key == K_ESCAPE):
                    going = False
                elif e.type == KEYDOWN:
                    if calibrating:
                        if not self.calibrate():
                            calibrating = False
                    else:
                        self.painting = not self.painting
                        print "Toggled paintbrush to %d" % self.painting
                        
            self.clock.tick(30)
                        
def usage():
    print "Semi-Automatic Paintbrush - by Nirav Patel <nrp@eclecti.cc>"
    print ""
    print "Uses an infrared camera, an InkShield, and your arm to"
    print "copy great works of art, or just any old picture."
    print ""
    print "Requires:"
    print "  InkShield http://nicholasclewis.com/projects/inkshield/"
    print "  Infrared LED on the ink cartridge"
    print "  A pygame supported camera modified for infrared."
    print ""
    print "Options:"
    print "  -h or --help       displays this helpful text"
    print "  -p or --port       the serial port the Arduino is on (optional)"
    print "  -w or --width      the width of the canvas in inches (8.0)"
    print "  -l or --height     the height of the canvas in inches (6.0)"
    print ""
    print "Usage:"
    print "  python paintbrush.py -p /dev/ttyUSB0 -w 6.0 -l 8.0 monalisa.jpg"
    print ""
    print "  Then follow the instructions in the console to calibrate and "
    print "  start drawing."

if __name__ == '__main__':
    serialport = None
    w = 6.0
    h = 8.0

    try:
        opts,args = getopt.gnu_getopt(sys.argv[1:], "hp:w:l:", ["help", "port=", "width=", "height="])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)
    
    for o,a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-p", "--port"):
            serialport = a
        elif o in ("-w", "--width"):
            w = float(a)
        elif o in ("-l", "--height"):
            h = float(a)
    
    if len(args) > 0:
        filename = args[0]
    else:
        usage()
        sys.exit(0)
        
    paintbrush = Paintbrush(filename, serialport, (w, h))
    paintbrush.run()
