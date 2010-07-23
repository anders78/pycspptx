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
    #Handle arguments
    cuda_args, count, retire, poison = handle_args(args)

    #Calculate threads and blocks
    (threads, blocks) = calcThreadsnBlocks(count)

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

    #Execute kernel
    hKernel(*cuda_args, block=(threads, 1, 1), grid=(blocks,1))
    end = time.time()
    print "Compile and execution time=", end-start

    #Pass outputs on to outputchannels. 
    #Check types, change output to
    #float if necessary
    if count > 0:
        if cuda_args[1].array[0] == instrs.tag['float']:
            cuda_args[1].array.dtype = numpy.float32
        for i in range(len(args)):
            if isinstance(args[i], ChannelEndWrite):
                for j in cuda_args[i].array[1:]:
                    args[i](j)
    if retire:
        raise ChannelRetireException  
    elif poison:
        raise ChannelPoisonException

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
                        tmp.extend([i()])
                        count += 1
                except ChannelRetireException:
                    retire = True
                except ChannelPoisonException:
                    poison = True
                except:
                    raise Exception('Unknown exception when reading from channel')
            
            if isinstance(tmp[0], int):
                cuda_args.append(cuda.In(numpy.array(tmp, numpy.int32)))
                compiler_args.append(['ChannelEndRead', 'int'])
            elif isinstance(tmp[0], float):
                cuda_args.append(cuda.In(numpy.array(tmp, numpy.float32)))
                compiler_args.append(['ChannelEndRead', 'float'])
        #Handle ChannelEndWrite
        elif isinstance(i, ChannelEndWrite):
            if count == 0:
                raise Exception('Read channels must be placed before write channels!')
            else:
                cuda_args.append(cuda.Out(numpy.array((count+1)*[0], numpy.int32)))
                compiler_args.append(['ChannelEndWrite', 'int'])
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


