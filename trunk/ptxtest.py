from subprocess import call
from pycsp.processes import *
from cudaprocess import *
import random
import time

s = "\n\
	.version 1.4\n\
	.target sm_10, map_f64_to_f32\n\
    .entry _Z8myKernelPi (\n\
		.param .u32 __cudaparm__Z8myKernelPi_data)\n\
	{\n\
	.reg .u16 %rh<4>;\n\
        .reg .u32 %r<8>;\n\
	mov.u16 	%rh1, %ctaid.x;\n\
	mov.u16 	%rh2, %ntid.x;\n\
	mul.wide.u16 	%r1, %rh1, %rh2;\n\
	cvt.u32.u16 	%r2, %tid.x;\n\
	add.u32 	%r3, %r2, %r1;\n\
	add.u32		%r7, %r3, 1;\n\
	ld.param.u32 	%r4, [__cudaparm__Z8myKernelPi_data];\n\
	mul.lo.u32 	%r5, %r3, 4;\n\
	add.u32 	%r6, %r4, %r5;\n\
	st.global.s32 	[%r6+0], %r7;\n\
	exit;\n\
	}\n\
"

@process
def producer(cout, count):
    x = 42.0
    for i in range(count):
        cout(x)
        x = x + 1.0
    retire(cout)

#sum = reduce(lambda x,y: x+(random()**2+random()**2<1.0), range(cnt))
@cudaprocess
def worker(cin, cout):
    while True:
        sum = reduce(lambda x,y: x+y, range(100))
        cout(sum)

@process
def consumer(cin):
    while True:
        val = cin()
        print val

c1 = Channel()
c2 = Channel()

start = time.time()
Parallel(producer(OUT(c1), 1024), worker(IN(c1), OUT(c2)), consumer(IN(c2)))
end = time.time()
print 'Time taken=', end-start
print "Done"
#Parallel(producer(OUT(c1), 1), worker(IN(c1)), consumer(IN(c2)))
#call(["../../bin/linux/release/ptxtest", s])


