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

#define a 16807
#define m 2147483647
#define q 127773
#define r 2836
#define conv (1.0/(m-1))
#
#long i
#
#double drandom()
#{
#  long l;
#
#  l = i/q;
#  i = a*(i-q*l)-r*l;
#  if (i<0) i+= m;
# 
#  k = floor((double) y*N/m);
#  y = j[k];
#  j[k] = i;
#  return conv*(y-1);
#}

t = "\n\
.version 2.0\n\
.target sm_20\n\
.reg .b32 divhelp<3>;\n\
.reg .b64 %tid_offset;\n\
.reg .b32 %t_id;\n\
.reg .v2 .b32 %seed;\n\
.func (.reg .v2 .b32 rval) random ()\n\
{\n\
        .reg .u64 localtmp;\n\
        .reg .f64 localtmp_f;\n\
        .reg .u32 k;\n\
//        add.u32 %seed.x, %seed.x, %t_id;\n\
        mul.wide.u32 localtmp, 1664525, %seed.x;\n\
        add.u64 localtmp, localtmp, 1013904223;\n\
        rem.u64 localtmp, localtmp, 4294967296;\n\
        cvt.u32.u64 %seed.x, localtmp;\n\
// //  k = floor((double) y*64/4294967296); \n\
//        mul.wide.u32 localtmp, %lcg_y, 64;\n\
//        cvt.rn.f64.u64 localtmp_f, localtmp;\n\
//        div.f64 localtmp_f, localtmp_f, 4294967296.0;\n\
//       cvt.rzi.u32.f64 k, localtmp_f;\n\
// //  y = j[k];\n\
//        mul.lo.u32 k, k, 4;\n\
//        add.u32 %lcg_j, %lcg_j, k;\n\
//        ld.global.u32 %lcg_y, [%lcg_j];\n\
// //  j[k] = i;\n\
//        st.global.u32 [%lcg_j], %seed.x;\n\
        cvt.rn.f32.u32 rval.x, %seed.x;\n\
        div.approx.f32 rval.x, rval.x, 4294967295.0;\n\
        mov.u32 rval.y, 2;\n\
//        mov.u32 rval.x, %seed.x;\n\
        ret;\n\
}\n\
.func (.reg .v2 .b32 %rval) lambda (.reg .v2 .b32 x, .reg .v2 .b32 y)\n\
.func (.reg .v2 .b32 rval) reduce (.reg .v2 .b32 list){\n\
        .reg .u32 len;\n\
        .reg .b32 tmp;\n\
        .reg .u32 pos;\n\
        .reg .u32 index;\n\
        .reg .v2 .b32 param<2>;\n\
        .reg .pred run;\n\
        .reg .pred typfloat;\n\
        setp.eq.u32 typfloat, list.y, 2;\n\
@typfloat bra.uni float;\n\
        ld.global.u32 len, [list];\n\
//        bra.uni typend;\n\
float:\n\
//        ld.const.f32 tmp, [list];\n\
//        cvt.rni.u32.f32 len, tmp;\n\
//typend:\n\
//        add.u32 list.x, list.x, 4;\n\
//        mov.u32 pos, 2;\n\
//        ld.const.b32 param0.x, [list];\n\
//        mov.u32 param0.y, list.y;\n\
//        add.u32 list.x, list.x, 4;\n\
//        ld.const.b32 param1.x, [list];\n\
//        mov.u32 param1.y, list.y;\n\
//        add.u32 list.x, list.x, 4;\n\
//        call.uni (rval), lambda, (param0, param1);\n\
//start:\n\
//        setp.lt.u32 run, pos, len;\n\
//  @!run bra.uni end;\n\
//        ld.const.b32 param1.x, [list];\n\
//        call.uni (rval), lambda, (rval, param1);\n\
//        add.u32 pos, pos, 1;\n\
//        add.u32 list.x, list.x, 4;\n\
//  @run bra.uni start;\n\
//end:\n\
        mov.b32 rval.x, len;\n\
        ret.uni;\n\
}\n\
.reg .b64 __cuda__cin_global;\n\
.func (.reg .v2 .b32 rval) cin (){\n\
	add.u64 __cuda__cin_global, __cuda__cin_global, %tid_offset;\n\
	ld.global.b32 rval.x, [__cuda__cin_global];\n\
	mov.s32 rval.y, 2;}\n\
\n\
.reg .b64 __cuda__cout_global;\n\
.func () cout (.reg .v2 .b32 val){\n\
	st.global.b32 [__cuda__cout_global], val.y;\n\
	add.u64 __cuda__cout_global, __cuda__cout_global, %tid_offset;\n\
	st.global.b32 [__cuda__cout_global+4], val.x;\n\
}\n\
.func (.reg .v2 .b32 %rval) lambda (\n\
	.reg .v2 .b32 x,\n\
	.reg .v2 .b32 y){\n\
.reg .v2 .b32 %tmp<12>;\n\
.reg .pred %pred<1>;\n\
	set.eq.u32.u32 %tmp1.x, x.y, 0;\n\
	mov.u32 %tmp1.y, 0;\n\
	and.b32 %tmp1.x, %tmp1.x, 1;\n\
	setp.gt.u32 %pred0, %tmp1.x, 0;\n\
@!%pred0	bra.uni %label0;\n\
	add.s32 %tmp4.x, x.x, y.x;\n\
	mov.u32 %tmp5.y, 0;\n\
	mov.s32 %tmp5.x, %tmp4.x;\n\
	mov.b32.v2 %tmp10, %tmp5;\n\
@%pred0	bra.uni %label1;\n\
%label0:\n\
	add.f32 %tmp8.x, x.x, y.x;\n\
	mov.u32 %tmp9.y, 2;\n\
	mov.f32 %tmp9.x, %tmp8.x;\n\
	mov.b32.v2 %tmp10, %tmp9;\n\
%label1:\n\
	mov.b32 %rval.x, %tmp10.x;\n\
	mov.s32 %rval.y, %tmp10.y;\n\
	ret.uni;\n\
}\n\
.entry worker (\n\
	.param .u64 __cudaparam__cin,\n\
	.param .u64 __cudaparam__cout){\n\
	.reg .pred %pred<1>;\n\
	.reg .v2 .b32 %tmp<12>;.reg .b32 %r<3>;\n\
	.reg .b16 %rh<3>;\n\
	mov.u16 %rh1, %ctaid.x;\n\
	mov.u16 %rh2, %ntid.x;\n\
	mul.wide.u16 %r1, %rh1, %rh2;\n\
	cvt.u32.u16 %r2, %tid.x;\n\
	add.u32 %t_id, %r2, %r1;\n\
	mul.wide.u32 %tid_offset, %t_id, 4;\n\
	add.u32 %r0, %t_id, 1937932349;\n\
	mov.u32 %seed.x, %r0;\n\
	call (%seed), random, ();\n\
	call (%seed), random, ();\n\
\n\
	.reg .v2 .b32 sum;\n\
	.reg .v2 .b32 x;\n\
	.reg .v2 .b32 y;\n\
	ld.param.u64 __cuda__cin_global, [__cudaparam__cin];\n\
	ld.param.u64 __cuda__cout_global, [__cudaparam__cout];\n\
	.global .s32 %tmp11_local[3] = {2, 1, 2};\n\
	mov.b32 %tmp11.x, %tmp11_local;\n\
	mov.u32 %tmp11.y, 0;\n\
	call.uni (sum), reduce, (%tmp11);\n\
	call.uni cout, (sum);\n\
}\n\
"

def execute(func, args):
#    dev = cuda.Device(0)
#    att = dev.get_attributes()
#    print att
    cuda_args = []
    ptx_args = []

    count = 0
    for i in args:
        if isinstance(i, ChannelEndRead):
            tmp = []
#            for e in range(threads*blocks):
#                print "HALLOOOO"
#                tmp.extend([i()])
            if count == 0: #first channel
                try:
                    while True:
                        tmp.extend([i()])
                        count += 1
                except:
                    pass
            
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

#    threads = 4
#    blocks = 1
    (threads, blocks) = calcThreadsnBlocks(count)
#    print "Running with threads = %s and blocks = %s" % (threads, blocks)
    #Make abstract syntax tree and create ptx from function
    st = ast.parse(inspect.getsource(func))

#    print "\nExplicating"
    explicator = ExplicateVisitor()
    st = explicator.visit(st)

#    print "\nFlattening"
    flatten = FlattenVisitor()
    st = flatten.visit(st)

#    print "\nInstruction selection"
    inst_selector = InstSelectVisitor()
    st = inst_selector.visit(st)

    color = {}
 #   pos = 0
 #   for r in instrs.varlist:
 #       color[r] = pos
 #       pos = pos + 1
    
#    liveness = LivenessVisitor()
#    liveness.visit(st)

#    interference = InterferenceVisitor(instrs.varlist.keys()+instrs.reserved_registers)
#    interference.visit(st)

#    color = interference.color_graph(color)

#    instrs.colornames = dict([(v, k) for (k, v) in color.iteritems()])
#    print "Color:", color

#    assignregisters = AssignRegistersVisitor(color)
#    st = assignregisters.visit(st)

#    print "\nGenerating PTX code:"
    ptx_generator = GenPTXVisitor()
    ptx = ptx_generator.visit(st)
#    print "\n"+ptx

#    print "Loading CUDA module from buffer"
    #Load cuda module and kernel to execute from generated ptx
#    cuda.Device(0).make_context(flags=cuda.ctx_flags.SCHED_AUTO)
#    hModule = cuda.module_from_buffer(t)
#    hKernel = hModule.get_function('worker')
    hModule = cuda.module_from_buffer(ptx)
    hKernel = hModule.get_function(instrs.entryFunc)

    #Execute kernel
#    print "Executing kernel"
    hKernel(*cuda_args, block=(threads, 1, 1), grid=(blocks,1))
#    print "Execution done"
    if cuda_args[1].array[0] == instrs.tag['float']:
        cuda_args[1].array.dtype = numpy.float32
#    print cuda_args[1].array[1:]
    for i in range(len(args)):
        if isinstance(args[i], ChannelEndWrite):
            for j in cuda_args[i].array[1:]:
                args[i](j)
            
#    print "cuda_args", cuda_args[1].array[1:]
#    print "ptx_args", ptx_args[1]
        
#    dev = cuda.Device(0)
#    att = dir(hKernel)#.get_attribute(NUM_REGS)
#    print "Registers used:", hKernel.num_regs
##############


#    #Calculate threads and blocks
#    threads, blocks = calcThreadsnBlocks(inputsize)
    
#    #Execute kernel
#    hKernel(*cuda_params, block=(1, 1, 1), grid=(1,1))

#    for i in range(len(params)):
#        if isinstance(params[i][1], ChannelEndWrite):
#            for j in cuda_params[i].array:
#                params[i][1](j)
        
#    print "cuda_params =",
#    for i in cuda_params:
#        print i.array,
#    print cuda_params[1].array

def message_handler(compile_success_bool, info_str, error_str):
    if compile_success_bool:
        print "Kernel compiled successfully"
    else:
        print "Info:", info_str
        print "Error:", error_str

def calcThreadsnBlocks(count):
    #Divide into blocks of 512 threads each
    if count % 512 == 0:
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


