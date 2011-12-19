""" Easy Interactive Camera-Projector Homography 

Copyright (c) 2010, Nirav Patel <http://eclecti.cc>

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

This script uses pygame and numpy to help you interactively calculate a 
camera-projector homography.  This allows you to translates points on
a camera to the correct location on a display, for purposes like a virtual
whiteboard using a projector, an IR camera, and an IR LED.  This file is
split into classes with the intent of being easy to pull apart and use
elsewhere.

FakeSource - A fake camera for testing purposes
IRCamera - Finds points using a pygame-supported IR Camera
WiiRemote - Finds points using a Wii Remote (unfinished)
PerspectiveTransform - Calculates a homography using four corner points
LeastSquaresTransform - Calculates a homography using four or more random points
Homography - Uses pygame to interactively calculate a camera-projector homography 
"""

__version__ = '0.1'
__author__ = 'Nirav Patel'

#!/usr/bin/env python

import sys
import random
import getopt
import numpy
from numpy import linalg
import pygame
try:
    import pygame.camera
    CAMERA_SUPPORT = True
except ImportError:
    print 'Camera support requires Pygame 1.9 or newer'
    CAMERA_SUPPORT = False 
from pygame.locals import *

class FakeSource:
    def __init__(self):
        self.count = 0
    
    def update(self):
        return pygame.surface.Surface((10,10),0)
        
    def get_point(self):
        ret = (0,0)
        if self.count == 0:
            ret = (15,140)
        elif self.count == 1:
            ret = (565,137)
        elif self.count == 2:
            ret = (29,447)
        elif self.count == 3:
            ret = (560,432)
        self.count += 1
        return ret

class IRCamera(FakeSource):
    """Interface an IR Camera in pygame
    
    update() -- Read in and return a new image from the camera
    get_point() -- Return the centroid of the largest IR blob found
    """
    
    def __init__(self):
        pygame.camera.init()
        
        # start the camera and find its resolution
        clist = pygame.camera.list_cameras()
        if len(clist) == 0:
            raise IOError('No cameras found.  The IRCamera class needs a camera supported by Pygame')
        self.resolution = (640,480)
        self.camera = pygame.camera.Camera(clist[0], self.resolution, "RGB")
        self.camera.start()
        # use the actual resolution, may or may not be the VGA asked for
        self.resolution = self.camera.get_size()
        self.snapshot = pygame.surface.Surface(self.resolution, 0)
        
    def update(self):
        """Read in and return a new image from the camera"""
        self.snapshot = self.camera.get_image(self.snapshot)
        return self.snapshot
        
    def get_point(self):
        """Return the centroid of the largest IR blob found"""
        mask = pygame.mask.from_threshold(self.snapshot, (255,255,255), (64,64,64))
        cc = mask.connected_component()
        # find the center of the dot, assuming its big enough to not be noise
        if cc.count() < 100:
            return None
        centroid = cc.centroid()
        return centroid
        
class WiiRemote(FakeSource):
    """Wii Remote interface not supported until I can find a good library.
    """
    
    def  __init__(self):
        pass
        
    def update(self):
        pass
        
    def get_point(self):
        pass

class PerspectiveTransform:
    """Calculates the perspective transform using 4 corner points
    
    generate_point() -- Generates the next screen point to use
    add_point(display, camera) -- Adds a matched pair of points
    calculate() -- Calculates the homography if there are 4 point pairs
    """
    
    def __init__(self, resolution):
        self.resolution = resolution
    
        # store the coordinates of the displayed and captured points
        self.display_points = []
        self.camera_points = []
        self.points = 4
        
    def generate_point(self):
        """Generates the next screen point to use"""
        count = len(self.display_points)
        
        # use the 4 corners of the screen for the perspective transform
        if count == 0:
            return (0,0)
        elif count == 1:
            return (self.resolution[0],0)
        elif count == 2:
            return (0, self.resolution[1])
        elif count == 3:
            return self.resolution
            
        return None
        
    def add_point(self, display, camera):
        """Adds a matched pair of points"""
        if len(self.display_points) < self.points:
            self.display_points.append(display)
            self.camera_points.append(camera)

        return len(self.display_points) != self.points
        
    def calculate(self):
        """Calculates the homography if there are 4+ point pairs"""
        n = len(self.display_points)
    
        if n < self.points:
            print 'Need 4 points to calculate transform'
            return None
        
        # This calculation is from the paper, A Plane Measuring Device
        # by A. Criminisi, I. Reid, A. Zisserman.  For more details, see:
        # http://www.robots.ox.ac.uk/~vgg/presentations/bmvc97/criminispaper/
        A = numpy.zeros((n*2,8))
        B = numpy.zeros((n*2,1))
        for i in range(0,n):
            A[2*i][0:2] = self.camera_points[i]
            A[2*i][2] = 1
            A[2*i][6] = -self.camera_points[i][0]*self.display_points[i][0]
            A[2*i][7] = -self.camera_points[i][1]*self.display_points[i][0]
            A[2*i+1][3:5] = self.camera_points[i]
            A[2*i+1][5] = 1
            A[2*i+1][6] = -self.camera_points[i][0]*self.display_points[i][1]
            A[2*i+1][7] = -self.camera_points[i][1]*self.display_points[i][1]
            B[2*i] = self.display_points[i][0]
            B[2*i+1] = self.display_points[i][1]
        
        X = linalg.lstsq(A,B)
        return numpy.reshape(numpy.vstack((X[0],[1])),(3,3))
    
class LeastSquaresTransform(PerspectiveTransform):
    """ Uses 4+ random points in the screen to calculate the transform
    """
    
    def generate_point(self):
        return (random.randint(0,self.resolution[0]), random.randint(0,self.resolution[1]))
        
    def add_point(self, display, camera):
        self.display_points.append(display)
        self.camera_points.append(camera)
        
        return len(self.display_points) < self.points
        
class Homography:
    def __init__(self, resolution, algorithm, source):
        pygame.mouse.set_visible(False)
        # set the display to its highest resolution at full screen
        display_resolutions = pygame.display.list_modes()
        self.display_res = display_resolutions[0]
        self.display = pygame.display.set_mode(self.display_res,pygame.FULLSCREEN)
        
        self.current_point = None
        
        self.source = source
        self.algorithm = algorithm
        
    def display_new_point(self):
        # blank out the display
        self.display.fill((0,0,0))
        pygame.display.flip()
        
    def update_display(self):
        rects = []
        
        # update the source display (ir image)
        surf = self.source.update()
        rects.append(self.display.blit(surf, (0,0)))
        pygame.draw.rect(self.display, (255,0,0), rects[0], 1)
        
        # draw crosshairs
        o = 25
        p = self.current_display_point
        rects.append(pygame.draw.rect(self.display, (0,255,0), pygame.Rect(p[0]-o,p[1]-o,o*2,o*2), 3))
        pygame.draw.line(self.display, (0,255,0), (p[0]-o,p[1]-o), (p[0]+o,p[1]+o), 1)
        pygame.draw.line(self.display, (0,255,0), (p[0]-o,p[1]+o), (p[0]+o,p[1]-o), 1)
        
        pygame.display.update(rects)
        
    def run(self):
        going = True
        self.current_display_point = self.algorithm.generate_point()
        print 'First display point ' + repr(self.current_display_point)
        self.display_new_point()
        
        while going:
            self.update_display()
            events = pygame.event.get()
            for e in events:
                if e.type == QUIT or (e.type == KEYDOWN and e.key == K_ESCAPE):
                    going = False
                elif e.type == KEYDOWN and e.key == K_RIGHT:
                    # skip the point if the key is right arrow
                    self.current_display_point = self.algorithm.generate_point()
                    if self.current_display_point:
                        print 'New display point ' + repr(self.current_display_point)
                        self.display_new_point()
                    else:
                        going = False
                elif e.type == KEYDOWN:
                    # any other key adds the point and goes to the next one
                    cam_point = self.source.get_point()
                    if cam_point:
                        enough = self.algorithm.add_point(self.current_display_point, cam_point)
                        print 'Point from source %s. Need more points? %s' % (repr(cam_point), repr(enough))
                        
                        self.current_display_point = self.algorithm.generate_point()
                        if self.current_display_point:
                            print 'New display point ' + repr(self.current_display_point)
                            self.display_new_point()
                        else:
                            going = False
                        
        homography = self.algorithm.calculate()
        return homography
        
def usage():
    print 'Interactively calculate a camera-projector homography.  Point an'
    print 'IR camera at a display, and run the script.  Align an IR LED,'
    print 'visible to the camera, over the green X on the display, and press'
    print 'any key.  After 4 points are found, and Escape is hit if using least'
    print 'squares mode, the script will calculate the camera-projector'
    print 'homography, print it out, and save it to the filename passed in as'
    print 'the first non-option argument'
    print ''
    print 'Options:'
    print ' -h or --help            Displays this help text'
    print ' -p or --perspective     Uses the 4 corner points (default)'
    print ' -l or --leastsquares    Uses 4+ random points'
    print ''
    print 'Usage:'
    print 'python homography.py matrix_file'
        
if __name__ == '__main__':
    matrix_file = 'homography'
    mode = 0
    
    try:
        opts,args = getopt.gnu_getopt(sys.argv[1:], "hpl", ["help", "perspective", "leastsquares"])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)
    
    for o,a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-p", "--perspective"):
            mode = 0
        elif o in ("-l", "--leastsquares"):
            mode = 1
    
    if len(args) > 0:
        matrix_file = args[0]

    pygame.init()
    display_resolutions = pygame.display.list_modes()
    resolution = display_resolutions[0]

    if mode == 0:
        algo = PerspectiveTransform(resolution)
    elif mode == 1:
        algo = LeastSquaresTransform(resolution)
    
#    source = FakeSource()
    if CAMERA_SUPPORT:
        source = IRCamera()
        
    if source:
        hom = Homography(resolution, algo, source)
        m = hom.run()
        print 'Saving matrix to %s.npy\n %s' % (matrix_file, repr(m))
        numpy.save(matrix_file,m)
    else:
        print 'No source found.'
