from pycsp.processes import *
from cudaprocess import *
import Image
import time

disp_width = 1024
disp_height = 1024

image = Image.new("I", [disp_width,disp_height])

@process
def producer(cout):
  for row in range(disp_height):
    cout(row)
  retire(cout)

@cudaprocess
def worker(cin, cout):
  #Globals, moved into scope
  real_min = -1.5
  imag_min = -1.5
  real_max = 1.5
  imag_max = 1.5
  disp_width = 1024
  disp_height = 1024
  scale_real = (real_max - real_min)/float(disp_width)
  scale_imag = (imag_max - imag_min)/float(disp_height)
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
      z_imag = 2.0 * z_real * z_imag + c[1]
      z_real = temp
      lengthsq = z_real * z_real + z_imag * z_imag
      count = count + 1
    return count
  c_real = 0.0
  c_imag = 0.0
  while True:
    y = cin()
    color = 1024*[None]
    c_imag = imag_min + float(y) * scale_imag
    x = 0
    while x < disp_width:
      c_real = real_min + float(x) * scale_real
      color[x] = cal_pixel([c_real, c_imag])
      x = x + 1
    y = [y]
    cout([y, color])

@process
def consumer(cin):
  try:
    while True:
      y, color = cin()
      for x in range(disp_height):
        image.putpixel((x, y[0]), color[x])
  except ChannelRetireException:
    image.show()

C1 = Channel()
C2 = Channel()

start = time.time()
Parallel(producer(C1.writer()), worker(C1.reader(), C2.writer()), consumer(C2.reader()))

end = time.time()
print "Time taken(s)=", end-start

