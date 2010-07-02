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

t = "\n\
.version 2.0\n\
.target sm_20\n\
.reg .b32 divhelp<3>;\n\
.reg .b64 %tid_offset;\n\
.reg .b32 %t_id;\n\
.reg .u32 seed;\n\
.func (.reg .f32 rval) random ()\n\
{\n\
        .reg .b32 l;\n\
        .reg .b32 tmp<2>;\n\
        .reg .pred less;\n\
        div.u32 l, seed, 127773;\n\
        mul.lo.u32 tmp0, l, 2836;\n\
        mul.lo.u32 tmp1, l, 127773;\n\
        sub.u32 tmp1, seed, tmp1;\n\
        mul.lo.u32 tmp1, 16807, tmp1;\n\
        sub.u32 seed, tmp1, tmp0;\n\
        setp.lt.u32 less, seed, 0;\n\
 @!less bra.uni notless;\n\
        add.u32 seed, seed, 2147483647;\n\
  notless:\n\
        sub.u32 tmp0, seed, 1;\n\
//        div.approx.f32 tmp1, 1.0, 2147483646.0;\n\
        mul.f32 rval, 4.65661287e-10, tmp0;\n\
//        div.approx.f32 rval, 1.0, 2147483646.0;\n\
//        mov.f32 rval, 4.65661287e-10;\n\
        ret.uni;\n\
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
        ld.const.u32 len, [list];\n\
        bra.uni typend;\n\
float:\n\
        ld.const.f32 tmp, [list];\n\
        cvt.rni.u32.f32 len, tmp;\n\
typend:\n\
        add.u32 list.x, list.x, 4;\n\
        mov.u32 pos, 2;\n\
        ld.const.b32 param0.x, [list];\n\
        mov.u32 param0.y, list.y;\n\
        add.u32 list.x, list.x, 4;\n\
        ld.const.b32 param1.x, [list];\n\
        mov.u32 param1.y, list.y;\n\
        add.u32 list.x, list.x, 4;\n\
        call.uni (rval), lambda, (param0, param1);\n\
start:\n\
        setp.lt.u32 run, pos, len;\n\
  @!run bra.uni end;\n\
        ld.const.b32 param1.x, [list];\n\
        call.uni (rval), lambda, (rval, param1);\n\
        add.u32 pos, pos, 1;\n\
        add.u32 list.x, list.x, 4;\n\
  @run bra.uni start;\n\
end:\n\
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
.entry worker (\n\
	.param .u64 __cudaparam__cin,\n\
	.param .u64 __cudaparam__cout){\n\
	.reg .pred %pred<0>;\n\
	.reg .v2 .b32 %tmp<0>;.reg .b32 %r<3>;\n\
	.reg .b16 %rh<3>;\n\
	mov.u16 %rh1, %ctaid.x;\n\
	mov.u16 %rh2, %ntid.x;\n\
	mul.wide.u16 %r1, %rh1, %rh2;\n\
	cvt.u32.u16 %r2, %tid.x;\n\
	add.u32 %t_id, %r2, %r1;\n\
	mul.wide.u32 %tid_offset, %t_id, 4;\n\
	mov.u32 seed, 1277718230376;\n\
\n\
	.reg .v2 .b32 res;\n\
	ld.param.u64 __cuda__cin_global, [__cudaparam__cin];\n\
	ld.param.u64 __cuda__cout_global, [__cudaparam__cout];\n\
        .reg .f32 tmp;\n\
	call.uni (tmp), random, ();\n\
        mov.f32 res.x, tmp;\n\
        mov.u32 res.y, 2;\n\
	call.uni cout, (res);\n\
}\n\
"

s = '.version 2.0\n\
.target sm_20\n\
.entry worker (\n\
	.param .u64 __cudaparam__cin,\n\
	.param .u64 __cudaparam__cout){\n\
	.reg .pred %pred<0>;\n\
	.reg .v2 .b32 %tmp<2>;.reg .b32 %r<3>;\n\
	.reg .b16 %rh<3>;\n\
\n\
	.reg .v2 .b32 l;\n\
	.local .s32 %tmp0_local[100];\n\
	mov.b32 %tmp0.x, %tmp0_local;\n\
	mov.u32 %tmp0.y, 0;\n\
        st.local.s32 [%tmp0+0], 0;\n\
        st.local.s32 [%tmp0+4], 1;\n\
        st.local.s32 [%tmp0+8], 2;\n\
        st.local.s32 [%tmp0+12], 3;\n\
        st.local.s32 [%tmp0+16], 4;\n\
        st.local.s32 [%tmp0+20], 5;\n\
        st.local.s32 [%tmp0+24], 6;\n\
        st.local.s32 [%tmp0+28], 7;\n\
        st.local.s32 [%tmp0+32], 8;\n\
        st.local.s32 [%tmp0+36], 9;\n\
        st.local.s32 [%tmp0+40], 10;\n\
        st.local.s32 [%tmp0+44], 11;\n\
        st.local.s32 [%tmp0+48], 12;\n\
        st.local.s32 [%tmp0+52], 13;\n\
        st.local.s32 [%tmp0+56], 14;\n\
        st.local.s32 [%tmp0+60], 15;\n\
        st.local.s32 [%tmp0+64], 16;\n\
        st.local.s32 [%tmp0+68], 17;\n\
        st.local.s32 [%tmp0+72], 18;\n\
        st.local.s32 [%tmp0+76], 19;\n\
        st.local.s32 [%tmp0+80], 20;\n\
        st.local.s32 [%tmp0+84], 21;\n\
        st.local.s32 [%tmp0+88], 22;\n\
        st.local.s32 [%tmp0+92], 23;\n\
        st.local.s32 [%tmp0+96], 24;\n\
        st.local.s32 [%tmp0+100], 25;\n\
        st.local.s32 [%tmp0+104], 26;\n\
        st.local.s32 [%tmp0+108], 27;\n\
        st.local.s32 [%tmp0+112], 28;\n\
        st.local.s32 [%tmp0+116], 29;\n\
        st.local.s32 [%tmp0+120], 30;\n\
        st.local.s32 [%tmp0+124], 31;\n\
        st.local.s32 [%tmp0+128], 32;\n\
        st.local.s32 [%tmp0+132], 33;\n\
        st.local.s32 [%tmp0+136], 34;\n\
        st.local.s32 [%tmp0+140], 35;\n\
        st.local.s32 [%tmp0+144], 36;\n\
        st.local.s32 [%tmp0+148], 37;\n\
        st.local.s32 [%tmp0+152], 38;\n\
        st.local.s32 [%tmp0+156], 39;\n\
        st.local.s32 [%tmp0+160], 40;\n\
        st.local.s32 [%tmp0+164], 41;\n\
        st.local.s32 [%tmp0+168], 42;\n\
        st.local.s32 [%tmp0+172], 43;\n\
        st.local.s32 [%tmp0+176], 44;\n\
        st.local.s32 [%tmp0+180], 45;\n\
        st.local.s32 [%tmp0+184], 46;\n\
        st.local.s32 [%tmp0+188], 47;\n\
        st.local.s32 [%tmp0+192], 48;\n\
        st.local.s32 [%tmp0+196], 49;\n\
        st.local.s32 [%tmp0+200], 50;\n\
        st.local.s32 [%tmp0+204], 1;\n\
        st.local.s32 [%tmp0+208], 2;\n\
        st.local.s32 [%tmp0+212], 3;\n\
        st.local.s32 [%tmp0+216], 4;\n\
        st.local.s32 [%tmp0+220], 5;\n\
        st.local.s32 [%tmp0+224], 6;\n\
        st.local.s32 [%tmp0+228], 7;\n\
        st.local.s32 [%tmp0+232], 8;\n\
        st.local.s32 [%tmp0+236], 9;\n\
        st.local.s32 [%tmp0+240], 10;\n\
        st.local.s32 [%tmp0+244], 11;\n\
        st.local.s32 [%tmp0+248], 12;\n\
        st.local.s32 [%tmp0+252], 13;\n\
        st.local.s32 [%tmp0+256], 14;\n\
        st.local.s32 [%tmp0+260], 15;\n\
        st.local.s32 [%tmp0+264], 16;\n\
        st.local.s32 [%tmp0+268], 17;\n\
        st.local.s32 [%tmp0+272], 18;\n\
        st.local.s32 [%tmp0+276], 19;\n\
        st.local.s32 [%tmp0+280], 20;\n\
        st.local.s32 [%tmp0+284], 21;\n\
        st.local.s32 [%tmp0+288], 22;\n\
        st.local.s32 [%tmp0+292], 23;\n\
        st.local.s32 [%tmp0+296], 24;\n\
        st.local.s32 [%tmp0+300], 25;\n\
        st.local.s32 [%tmp0+304], 26;\n\
        st.local.s32 [%tmp0+308], 27;\n\
        st.local.s32 [%tmp0+312], 28;\n\
        st.local.s32 [%tmp0+316], 29;\n\
        st.local.s32 [%tmp0+320], 30;\n\
        st.local.s32 [%tmp0+324], 31;\n\
        st.local.s32 [%tmp0+328], 32;\n\
        st.local.s32 [%tmp0+332], 33;\n\
        st.local.s32 [%tmp0+336], 34;\n\
        st.local.s32 [%tmp0+340], 35;\n\
        st.local.s32 [%tmp0+344], 36;\n\
        st.local.s32 [%tmp0+348], 37;\n\
        st.local.s32 [%tmp0+352], 38;\n\
        st.local.s32 [%tmp0+356], 39;\n\
        st.local.s32 [%tmp0+360], 40;\n\
        st.local.s32 [%tmp0+364], 41;\n\
        st.local.s32 [%tmp0+368], 42;\n\
        st.local.s32 [%tmp0+372], 43;\n\
        st.local.s32 [%tmp0+376], 44;\n\
        st.local.s32 [%tmp0+380], 45;\n\
        st.local.s32 [%tmp0+384], 46;\n\
        st.local.s32 [%tmp0+388], 47;\n\
        st.local.s32 [%tmp0+392], 48;\n\
        st.local.s32 [%tmp0+396], 49;\n\
        st.local.s32 [%tmp0+400], 50;\n\
	mov.b32.v2 l, %tmp0;\n\
	ld.global.b32 %tmp1.x, [l+4];\n\
	mov.b32 %tmp1.y, l.y;\n\
}'

def execute(func, args):
    #dev = cuda.Device(0)
    #att = dev.get_attributes()
    #print att
    cuda_args = []
    ptx_args = []
    threads = 512
    blocks = 1
    for i in args:
        if isinstance(i, ChannelEndRead):
            tmp = []
            for e in range(threads*blocks):
#                print "HALLOOOO"
                tmp.extend([i()])
            if isinstance(tmp[0], int):
                cuda_args.append(cuda.In(numpy.array(tmp, numpy.int32)))
                ptx_args.append(['ChannelEndRead', 'int'])
            elif isinstance(tmp[0], float):
                cuda_args.append(cuda.In(numpy.array(tmp, numpy.float32)))
                ptx_args.append(['ChannelEndRead', 'float'])
#            ptx_args.append(['','ChannelEndRead', tmp])

        elif isinstance(i, ChannelEndWrite):
            #TODO: Get type for output
            cuda_args.append(cuda.Out(numpy.array((threads*blocks+1)*[0], numpy.int32)))
            ptx_args.append(['ChannelEndWrite', 'int'])
        elif isinstance(i, int):
            ptx_args.append(['int',i])
        elif isinstance(i, float):
            ptx_args.append(['float',i])
        else:
            raise Exception('Unknown argument type %s' %i)
    instrs.args = ptx_args

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
#    hModule = cuda.module_from_buffer(s)
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
    #TODO
    return count, 1


