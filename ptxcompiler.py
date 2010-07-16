import inspect
import ast
import pycuda.driver as cuda
import pycuda.autoinit
import numpy
from pycsp.processes.channelend import ChannelEndRead, ChannelEndWrite
from explicatevisitor import *
from flattenvisitor import *
from instselectvisitor import *
from genptxvisitor import *
import instrs

from pycsp.processes.channel import ChannelRetireException, ChannelPoisonException

def execute(func, args):
#    dev = cuda.Device(0)
#    att = dev.get_attributes()
#    print att
    cuda_args = []
    ptx_args = []
    retire = poison = False

    count = 0
    for i in args:
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
                ptx_args.append(['ChannelEndRead', 'int'])
            elif isinstance(tmp[0], float):
                cuda_args.append(cuda.In(numpy.array(tmp, numpy.float32)))
                ptx_args.append(['ChannelEndRead', 'float'])
#            ptx_args.append(['','ChannelEndRead', tmp])

        elif isinstance(i, ChannelEndWrite):
            #TODO: Get type for output
            if count == 0:
                raise Exception('Read channels must be placed before write channels!')
            else:
                cuda_args.append(cuda.Out(numpy.array((count+1)*[0], numpy.int32)))
                ptx_args.append(['ChannelEndWrite', 'int'])
                #cuda_args.append(cuda.Out(numpy.array((threads*blocks+1)*[0], numpy.int32)))
                #ptx_args.append(['ChannelEndWrite', 'int'])
        elif isinstance(i, int):
            ptx_args.append(['int',i])
        elif isinstance(i, float):
            ptx_args.append(['float',i])
        else:
            raise Exception('Unknown argument type %s' %i)
    instrs.args = ptx_args

#    threads = 1
#    blocks = 1
    (threads, blocks) = calcThreadsnBlocks(count)
#    print threads, blocks
#    print "Running with threads = %s and blocks = %s" % (threads, blocks)
    #Make abstract syntax tree and create ptx from function
    st = ast.parse(inspect.getsource(func))

#    print "\nExplicating"
#    start = time.time()
    explicator = ExplicateVisitor()
    st = explicator.visit(st)
#    end = time.time()
#    print 'Time taken to explicate=', end-start

#    print "\nFlattening"
#    start = time.time()
    flatten = FlattenVisitor()
    st = flatten.visit(st)
#    end = time.time()
#    print 'Time taken to flatten=', end-start

#    print "\nInstruction selection"
#    start = time.time()
    inst_selector = InstSelectVisitor()
    st = inst_selector.visit(st)
#    end = time.time()
#    print 'Time taken to instselect=', end-start

#    print "\nGenerating PTX code:"
#    start = time.time()
    ptx_generator = GenPTXVisitor()
    ptx = ptx_generator.visit(st)
#    end = time.time()
#    print 'Time taken to genptx=', end-start
#    print "\n"+ptx

#    print "Loading CUDA module from buffer"
    #Load cuda module and kernel to execute from generated ptx
#    cuda.Device(0).make_context(flags=cuda.ctx_flags.SCHED_AUTO)
#    hModule = cuda.module_from_buffer(t)
#    hKernel = hModule.get_function('worker')
    start = time.time()
    hModule = cuda.module_from_buffer(ptx)
    hKernel = hModule.get_function(instrs.entryFunc)
#    end = time.time()
#    print 'Time taken to load module=', end-start

    #Execute kernel
#    print "Executing kernel"
#    start = time.time()
    hKernel(*cuda_args, block=(threads, 1, 1), grid=(blocks,1))
    end = time.time()
    print 'Time taken to execute=', end-start
#    print "Execution done"
    if count > 0:
        if cuda_args[1].array[0] == instrs.tag['float']:
            cuda_args[1].array.dtype = numpy.float32
    #    print cuda_args[1].array[1:]
        for i in range(len(args)):
            if isinstance(args[i], ChannelEndWrite):
                for j in cuda_args[i].array[1:]:
                    args[i](j)
    if retire:
        raise ChannelRetireException  
    elif poison:
        raise ChannelPoisonException
#    print "cuda_args", cuda_args[1].array[1:]
#    print "ptx_args", ptx_args[1]
        
#    dev = cuda.Device(0)
#    att = dir(hKernel)#.get_attribute(NUM_REGS)
#    print "Registers used:", hKernel.num_regs

def message_handler(compile_success_bool, info_str, error_str):
    if compile_success_bool:
        print "Kernel compiled successfully"
    else:
        print "Info:", info_str
        print "Error:", error_str

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
    else:
        raise Exception('Number of input must be divisible by 64!')
    return (t, count / t)


