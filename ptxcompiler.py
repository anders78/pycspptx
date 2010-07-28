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

#Handles arguments, applies compiler passes to function, and executes resulting
#PTX code on the device
def execute(func, args):
    #Handle arguments for the compiler
    handle_compileargs(args)

    #Parse source code of function to create AST
    start = time.time()
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

    #Load CUDA module from PTX string
    hModule = cuda.module_from_buffer(ptx)
    #Set entry function
    hKernel = hModule.get_function(instrs.entryFunc)

    #Create CUDA arguments, ie. arrays for input/output
    cuda_args, count, retire, poison = handle_cudaargs(args)

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
                print cuda_args[i].array[0][1]
                if instrs.tag['float'] == cuda_args[i].array[0][1]:
                    cuda_args[i].array.dtype = (numpy.float32,numpy.int32)
                for (j,k) in cuda_args[i].array:
                    args[i](j)
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
                                tmp.extend([elem_gpu, instrs.tag['float']])
                            elif isinstance(elem[0], int):
                                cuda.memcpy_htod(elem_gpu, numpy.array([len(elem)]+list(elem), numpy.int32))
                                tmp.extend([elem_gpu, instrs.tag['int']])
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
            if type(elem).__name__ == 'int' or type(elem).__name__ == 'list':
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
                

#Handle arguments. Important! Input channels must be placed before output channels!
#Also, number of elements recieved on input, must be the same as the number
#of elements sent on output.
def handle_args(args):
    #cuda_args are the arguments placed in a NumPy array, and passed to the device
    cuda_args = []

    #compiler_args are arguments passed to the compiler, describing the types
    #of the cuda_args
    compiler_args = []
    count = 0
    retire = poison = False

    for i in args:
        #Handle ChannelEndRead
        if isinstance(i, ChannelEndRead):
            tmp = []
            if count == 0: #first channel
                try:
                    while True:
                        tmp.extend([(i(),0)])
                        count += 1
                except ChannelRetireException:
                    retire = True
                except ChannelPoisonException:
                    poison = True
                except:
                    raise Exception('Unknown exception when reading from channel')
            
#            if isinstance(tmp[0], int):
            cuda_args.append(cuda.In(numpy.array(tmp, numpy.dtype('i4','i4'))))
            compiler_args.append(['ChannelEndRead', 'int'])
 #           elif isinstance(tmp[0], float):
 #               cuda_args.append(cuda.In(numpy.array(tmp, numpy.float32)))
  #              compiler_args.append(['ChannelEndRead', 'float'])
        #Handle ChannelEndWrite
        elif isinstance(i, ChannelEndWrite):
            if count == 0:
                raise Exception('Read channels must be placed before write channels!')
            else:
#                cuda_args.append(cuda.Out(numpy.array((count)*[0], (numpy.int32, numpy.int32))))
                cuda_args.append(cuda.Out(numpy.array(count*[(0,0)], numpy.dtype('i4','i4'))))
                compiler_args.append(['ChannelEndWrite', ''])
        #Handle int argument
        elif isinstance(i, int):
            compiler_args.append(['int',i])
        #Handle float argument
        elif isinstance(i, float):
            compiler_args.append(['float',i])
        else:
            raise Exception('Unknown argument type %s' %i)
    #Pass compiler_args to instrs helper.
    instrs.args = compiler_args
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


