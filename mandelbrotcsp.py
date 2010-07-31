from pycsp.processes import *
from cudaprocess import *
import Image
import time

disp_width = 1792
disp_height = disp_width

(real_min, imag_min) = (-2.0,-2.0)
(real_max, imag_max) = (2.0,2.0)

scale_real = (real_max - real_min)/disp_width
scale_imag = (imag_max - imag_min)/disp_height

image = Image.new("I", [disp_width,disp_height])

def cal_pixel(c):
  z_real = 0.0
  z_imag = 0.0

  temp = c[0]
  z_imag =c[1]
  z_real = temp
  lengthsq = z_real * z_real + z_imag * z_imag
  count = 1

  while ((lengthsq < 4.0) and (count < 256)):
    temp = z_real * z_real - z_imag * z_imag + c[0]
    z_imag = 2 * z_real * z_imag + c[1]
    z_real = temp
    lengthsq = z_real * z_real + z_imag * z_imag
    count = count + 1
  return count

@process
def producer(cout):
  for row in range(disp_height):
    cout(row)
  retire(cout)

@process
def worker(cin, cout):
  c_real = 0.0
  c_imag = 0.0
  while True:
    y = cin()
    color = disp_width*[None]
    c_imag = imag_min + float(y) * scale_imag
    x = 0
    while x < disp_width:
      c_real = real_min + float(x) * scale_real
      color[x] = cal_pixel([c_real, c_imag])
      x = x + 1
    cout([y,color])

@process
def consumer(cin):
  try:
    while True:
      (y, color) = cin()
      for x in range(disp_width):
        image.putpixel((x, y), color[x])
  except ChannelRetireException:
    pass
#      image.show()

C1 = Channel()
C2 = Channel()

start = time.time()
Parallel(producer(C1.writer()), 3*worker(C1.reader(), C2.writer()), consumer(C2.reader()))

end = time.time()
print "Time taken(s)=", end-start

