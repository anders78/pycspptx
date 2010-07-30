import inspect
import ast
import pycuda.autoinit
import pycuda.driver as cuda
import numpy
from pycsp.processes.channelend import ChannelEndRead, ChannelEndWrite
from explicatevisitor import *
from flattenvisitor import *
from instselectvisitor import *
from genptxvisitor import *
import instrs
import time
from pycsp.processes.channel import ChannelRetireException, ChannelPoisonException

s = '.version 2.0\n\
.target sm_20\n\
.reg .b32 divhelp<3>;\n\
.reg .b64 %tid_offset;\n\
.reg .b64 %tid_offseth;\n\
.reg .b32 %t_id;\n\
.reg .v2 .b32 %seed;\n\
\n\
.reg .b64 __cuda__cin_global;\n\
        .func (.reg .v2 .b32 rval) cin (){\n\
        	add.u64 __cuda__cin_global, __cuda__cin_global, %tid_offset;\n\
        	ld.global.v2.b32 rval, [__cuda__cin_global];\n\
}\n\
\n\
.reg .b64 __cuda__cout_global;\n\
        .func () cout (.reg .v2 .b32 val){\n\
        	add.u64 __cuda__cout_global, __cuda__cout_global, %tid_offset;\n\
        	st.global.v2.b32 [__cuda__cout_global], val;\n\
}\n\
\n\
.entry worker(\n\
	.param .u64 __cudaparam__cin, \n\
	.param .u64 __cudaparam__cout)\n\
{\n\
	.reg .b32 %r<3>;\n\
	.reg .b16 %rh<3>;\n\
	mov.u16 %rh1, %ctaid.x;\n\
	mov.u16 %rh2, %ntid.x;\n\
	mul.wide.u16 %r1, %rh1, %rh2;\n\
	cvt.u32.u16 %r2, %tid.x;\n\
	add.u32 %t_id, %r2, %r1;\n\
	mul.wide.u32 %tid_offseth, %t_id, 4;\n\
	mul.wide.u32 %tid_offset, %t_id, 8;\n\
\n\
	.reg .v2 .b32 a;\n\
	.reg .v2 .b32 x;\n\
	.reg .v2 .b32 b;\n\
	.reg .v2 .b32 l2;\n\
	.reg .v2 .b32 %tmp<1>;\n\
	.reg .pred %pred<0>;\n\
	ld.param.u64 __cuda__cin_global, [__cudaparam__cin];\n\
	ld.param.u64 __cuda__cout_global, [__cudaparam__cout];\n\
	call (x), cin, ();\n\
	ld.b32 a.x, [x+4];\n\
	mov.b32 a.y, x.y;\n\
	sub.s32 a.y, x.y, 2;\n\
	ld.b32 b.x, [x+8];\n\
	mov.b32 b.y, x.y;\n\
	sub.s32 b.y, x.y, 2;\n\
	.global.b32 %tmp0_local[96];\n\
        .reg .u32 offset;\n\
	mov.b32 %tmp0.x, %tmp0_local;\n\
        mul.lo.u32 offset, %t_id, 3;\n\
        mul.lo.u32 offset, offset, 4;\n\
        add.u32 %tmp0.x, %tmp0.x, offset;\n\
	mov.u32 %tmp0.y, a.y;\n\
	add.u32 %tmp0.y, %tmp0.y, 2;\n\
	st.global.b32 [%tmp0+0], 2;\n\
	st.global.b32 [%tmp0+4], a;\n\
	st.global.b32 [%tmp0+8], b;\n\
	mov.b32.v2 l2, %tmp0;\n\
	call cout, (l2);\n\
}'

#Handles arguments, applies compiler passes to function, and executes resulting
#PTX code on the device
def execute(func, args):
    #Handle arguments for the compiler
    handle_compileargs(args)

    #Create CUDA arguments, ie. arrays for input/output
    cuda_args, count, retire, poison = handle_cudaargs(args)
    instrs.threads = count

    #Parse source code of function to create AST
    st = ast.parse(inspect.getsource(func))

    #Explicate AST
    explicator = ExplicateVisitor()
    st = explicator.visit(st)

    #Flatten explicated AST
    flatten = FlattenVisitor()
    st = flatten.visit(st)

    #Create AST of PTX instruction nodes
    inst_selector = InstSelectVisitor()
    st = inst_selector.visit(st)

    #Generate PTX string from AST of 
    #instruction nodes
    ptx_generator = GenPTXVisitor()
    ptx = ptx_generator.visit(st)
#    print ptx
    start = time.time()

    #Load CUDA module from PTX string
    hModule = cuda.module_from_buffer(ptx)

    end = time.time()
    print "Time to gen ptx:", end-start
    #Set entry function
    hKernel = hModule.get_function(instrs.entryFunc)

    #Calculate threads and blocks
    (threads, blocks) = calcThreadsnBlocks(count)
    #Execute kernel

    hKernel(*cuda_args, block=(threads, 1, 1), grid=(blocks,1))
    #Pass outputs on to outputchannels. 
    #Check types, change output to
    #float if necessary
    if count > 0:
        for i in range(len(args)):
            if isinstance(args[i], ChannelEndWrite):
                typ = cuda_args[i].array[0][1]
                if instrs.tag['float'] == typ:
                    cuda_args[i].array.dtype = (numpy.float32,numpy.int32)
                    for (j,k) in cuda_args[i].array:
                        args[i](j)
                elif instrs.tag['int'] == typ:
                    for (j,k) in cuda_args[i].array:
                        args[i](j)
                elif instrs.tag['intlist'] == typ:
                    for (j,k) in cuda_args[i].array:
                        arr = cuda.from_device(int(j),1,numpy.int32)
                        arr = cuda.from_device(int(j+4),arr,numpy.int32)
                        args[i](arr)
                elif instrs.tag['floatlist'] == typ:
                    for (j,k) in cuda_args[i].array:
                        arr = cuda.from_device(int(j),1,numpy.int32)
                        if arr > 1000000000: #Fix since length may be written as float
                            arr = cuda.from_device(int(j),1,numpy.float32)
                        arr = cuda.from_device(int(j+4),int(arr),numpy.float32)
                        args[i](arr)
    if retire:
        raise ChannelRetireException  
    elif poison:
        raise ChannelPoisonException

def handle_compileargs(args):
    for i in args:
        if isinstance(i,ChannelEndRead):
            instrs.args.append(['ChannelEndRead', None])
        elif isinstance(i,ChannelEndWrite):
            instrs.args.append(['ChannelEndWrite', None])
        #Handle int argument
        elif isinstance(i, int):
            instrs.args.append(['int',i])
        #Handle float argument
        elif isinstance(i, float):
            instrs.args.append(['float',i])
        else:
            raise Exception('Unknown argument type %s' %i)

def handle_cudaargs(args):
    cuda_args = len(instrs.args)*[None]
    count = 0
    poison = retire = False
    #Two passes, first handle input channels, then output channels
    for i in range(len(args)):
        if isinstance(args[i], ChannelEndRead):
            tmp = []
            bits = 0
            if count == 0: #First channel
                try:
                    while True:
                        elem = args[i]()
                        #Bug in PyCUDA, malloc must be "warmed up"
                        elem_gpu = cuda.mem_alloc(1)
                        if isinstance(elem, tuple) or isinstance(elem, list):
                            elem_gpu = cuda.mem_alloc((len(elem)+1)*4)
                            if isinstance(elem[0], float):
                                cuda.memcpy_htod(elem_gpu, numpy.array([len(elem)]+list(elem), numpy.float32))
                                tmp.extend([elem_gpu, instrs.tag['floatlist']])
                            elif isinstance(elem[0], int):
                                cuda.memcpy_htod(elem_gpu, numpy.array([len(elem)]+list(elem), numpy.int32))
                                tmp.extend([elem_gpu, instrs.tag['intlist']])
                            count += 1
                            bits = 4
                        else:
                            tmp.extend([elem, instrs.tag[type(elem).__name__]])
                            count += 1
                            bits = 4
                except ChannelRetireException:
                    retire = True
                except ChannelPoisonException:
                    poison = True
            if type(elem).__name__ == 'int' or \
               type(elem).__name__ == 'list' or \
               type(elem).__name__ == 'tuple':
                cuda_args[i] = (cuda.In(numpy.array(tmp, numpy.dtype('i4','i4'))))
            elif type(elem).__name__ == 'float':
                cuda_args[i] = (cuda.In(numpy.array(tmp, numpy.dtype('f4','i4'))))

    for i in range(len(args)):
        if isinstance(args[i], ChannelEndWrite):
            if count == 0:
                raise Exception('Process must contain read channels')
            else:
                cuda_args[i] = cuda.Out(numpy.array((count)*[(0,0)], (numpy.int32,numpy.int32)))


    return cuda_args, count, retire, poison
                
def calcThreadsnBlocks(count):
    #Divide into blocks of 512 threads each
    if count == 0:
        return (1,1)
    elif count % 1024 == 0:
        t = 1024
    elif count % 512 == 0:
        t = 512
    elif count % 256 == 0:
        t = 256
    elif count % 128 == 0:
        t = 128
    elif count % 64 == 0:
        t = 64
    elif count % 32 == 0:
        t = 32
    else:
        raise Exception('Number of input must be divisible by 32!')
    return (t, count / t)


