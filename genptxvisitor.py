import ast
from instrs import *
import time
from random import *

class GenPTXVisitor(ast.NodeVisitor):
    def __init__(self):
        self.varlist = {}

    def make_ChannelEndRead(self, name, typ):
        func = '\n.reg .b64 __cuda__%s_global;\n' % name
        func = func + '.func (.reg .v2 .b32 rval) %s (){\n' % name
        func = func + '\tadd.u64 __cuda__%s_global, __cuda__%s_global, %%tid_offset;\n' % (name, name)
        func = func + '\tld.global.b32 rval.x, [__cuda__%s_global];\n' % name
        func = func + '\tmov.s32 rval.y, %s;}\n' % instrs.tag[typ]
        return func

    def make_ChannelEndWrite(self, name, typ):
        func = '\n.reg .b64 __cuda__%s_global;\n' % name
        func = func + '.func () %s (.reg .v2 .b32 val){\n' % name
        func = func + '\tst.global.b32 [__cuda__%s_global], val.y;\n' % name
        func = func + '\tadd.u64 __cuda__%s_global, __cuda__%s_global, %%tid_offset;\n' % (name, name)
        func = func + '\tst.global.b32 [__cuda__%s_global+4], val.x;\n}' % name
        return func
#OLD RANDOM FUNCTION    
#.func (.reg .v2 .b32 rval) random ()\n\
#{\n\
#        .reg .u64 localtmp;\n\
#        .reg .f64 localtmp_f;\n\
#        .reg .u32 k;\n\
#//        add.u32 %seed, %seed, %t_id;\n\
#        mul.wide.u32 localtmp, 1664525, %seed;\n\
#        add.u64 localtmp, localtmp, 1013904223;\n\
#        rem.u64 localtmp, localtmp, 4294967296;\n\
#        cvt.u32.u64 %seed, localtmp;\n\
#// //  k = floor((double) y*64/4294967296); \n\
#//        mul.wide.u32 localtmp, %lcg_y, 64;\n\
#//        cvt.rn.f64.u64 localtmp_f, localtmp;\n\
#//        div.f64 localtmp_f, localtmp_f, 4294967296.0;\n\
#//       cvt.rzi.u32.f64 k, localtmp_f;\n\
#// //  y = j[k];\n\
#//        mul.lo.u32 k, k, 4;\n\
#//        add.u32 %lcg_j, %lcg_j, k;\n\
#//        ld.global.u32 %lcg_y, [%lcg_j];\n\
#// //  j[k] = i;\n\
#//        st.global.u32 [%lcg_j], %seed;\n\
#        cvt.rn.f32.u32 rval.x, %seed;\n\
#        div.approx.f32 rval.x, rval.x, 4294967295.0;\n\
#        mov.u32 rval.y, 2;\n\
#//        mov.u32 rval.x, %seed;\n\
#        ret.uni;\n\
#}\n\

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

    def visit_Module(self, node):
        stmts = ''
        preamble = '\n.version 2.0\n.target sm_20\n'
        self.funcs = '\
.reg .b32 divhelp<3>;\n\
.reg .b64 %tid_offset;\n\
.reg .b32 %t_id;\n\
.reg .v2 .b32 %seed;\n\
.func (.reg .v2 .b32 rval) random ()\n\
{\n\
        .reg .u64 localtmp;\n\
        .reg .f64 localtmp_f;\n\
        .reg .u32 k;\n\
        mul.wide.u32 localtmp, 1664525, %seed.x;\n\
        add.u64 localtmp, localtmp, 1013904223;\n\
        rem.u64 localtmp, localtmp, 4294967296;\n\
        cvt.u32.u64 %seed.x, localtmp;\n\
        cvt.rn.f32.u32 rval.x, %seed.x;\n\
        div.approx.f32 rval.x, rval.x, 4294967295.0;\n\
        mov.u32 rval.y, 2;\n\
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
        bra.uni typend;\n\
float:\n\
        ld.global.f32 tmp, [list];\n\
        cvt.rni.u32.f32 len, tmp;\n\
typend:\n\
        add.u32 list.x, list.x, 4;\n\
        mov.u32 pos, 2;\n\
        ld.global.b32 param0.x, [list];\n\
        mov.u32 param0.y, list.y;\n\
        add.u32 list.x, list.x, 4;\n\
        ld.global.b32 param1.x, [list];\n\
        mov.u32 param1.y, list.y;\n\
        add.u32 list.x, list.x, 4;\n\
        call.uni (rval), lambda, (param0, param1);\n\
start:\n\
        setp.lt.u32 run, pos, len;\n\
  @!run bra.uni end;\n\
        ld.global.b32 param1.x, [list];\n\
        call.uni (rval), lambda, (rval, param1);\n\
        add.u32 pos, pos, 1;\n\
        add.u32 list.x, list.x, 4;\n\
  @run bra.uni start;\n\
end:\n\
        ret.uni;\n\
}'
        
#        for i in node.body:
 #           stmts = stmts + visit(self, i)
        stmts = stmts + ''.join([visit(self,i) for i in node.body])
        return preamble + self.funcs + stmts

    def visit_FunctionDef(self, node):
        old_varlist = self.varlist
        args = ''
        stmts = ''
        if instrs.entryFunc == node.name:
            for i in range(len(node.args.args)):
                if instrs.args[i][0] == 'ChannelEndRead' or instrs.args[i][0] == 'ChannelEndWrite':
                    if i > 0:
                        args = args + ','
                    args = args + '\n\t.param .u64 __cudaparam__' + node.args.args[i].id
                    if instrs.args[i][0] == 'ChannelEndRead':
                        self.funcs = self.funcs + self.make_ChannelEndRead(node.args.args[i].id, instrs.args[i][1])
                        stmts = stmts + '\n\tld.param.u64 __cuda__%s_global, [__cudaparam__%s];' % (node.args.args[i].id, node.args.args[i].id)
                    if instrs.args[i][0] == 'ChannelEndWrite':
                        self.funcs = self.funcs + self.make_ChannelEndWrite(node.args.args[i].id, instrs.args[i][1])
                        stmts = stmts + '\n\tld.param.u64 __cuda__%s_global, [__cudaparam__%s];' % (node.args.args[i].id, node.args.args[i].id)
#            for i in node.body:
#               stmts = stmts + visit(self, i)
            stmts = stmts + ''.join([visit(self,i) for i in node.body])
 
            for i in self.varlist:
                stmts = '\n\t.reg .v2 .%s %s;' % (self.varlist[i], i) + stmts
            self.var_list = old_varlist
	    stmts = '.reg .b32 %r<3>;\n\
\t.reg .b16 %rh<3>;\n\
\tmov.u16 %rh1, %ctaid.x;\n\
\tmov.u16 %rh2, %ntid.x;\n\
\tmul.wide.u16 %r1, %rh1, %rh2;\n\
\tcvt.u32.u16 %r2, %tid.x;\n\
\tadd.u32 %t_id, %r2, %r1;\n\
\tmul.wide.u32 %tid_offset, %t_id, 4;\n\
\tadd.u32 %r0, %t_id, ' + str(randint(0,4294967295)) + ';\n\
\tmov.u32 %seed.x, %r0;\n\
\tcall (%seed), random, ();\n\
\tcall (%seed), random, ();\n' + stmts

            stmts = '\n\t.reg .v2 .b32 %tmp<'+str(instrs.tmpcounter)+'>;' + stmts
            stmts = '\n\t.reg .pred %pred<'+str(instrs.predcounter)+'>;'  + stmts
            return '\n.entry %s (%s){%s\n}' % (node.name, args, stmts)
        else:
            for i in range(len(node.args.args)):
                args = args + '\n\t.reg .v2 .b32 ' + node.args.args[i].id
                self.varlist[node.args.args[i].id] = 'b32'
                if i < len(node.args.args)-1:
                    args = args + ','
            body = ''
#            for i in node.body:
#                body = body + visit(self, i)
            body = body + ''.join([visit(self,i) for i in node.body])

            self.funcs = self.funcs + '\n.func (%s) %s (%s){' % ('.reg .v2 .b32 %rval', node.name, args)
            self.var_list = old_varlist
            stmts = stmts + '\n.reg .v2 .b32 %tmp<'+str(instrs.tmpcounter)+'>;'
            stmts = stmts + '\n.reg .pred %pred<'+str(instrs.predcounter)+'>;'
            self.funcs = self.funcs +stmts+ body +'\n}'
            return ''

    def visit_DeclareArray(self, node):
        name = visit(self, node.name)
        if isinstance(node.elems[1].n, float):
            typ = '.f32'
            l = float(node.elems[0].n)
        elif isinstance(node.elems[1].n, int):
            typ = '.s32'
            l = int(node.elems[0].n)
        else:
            raise Exception ('Unsupported element type in list %s' % node.name.id)

#return ''.join([`num` for num in range(loop_count)])

        elems = '{'+str(l)
#        for i in node.elems[1:]:
 #           elems = elems + ', '+str(i.n)
        elems = elems + ''.join([','+`i.n` for i in node.elems[1:]]) +'}'
        string = '\n\t.global %s %s[%s] = %s;' % (typ, name+'_local', len(node.elems), elems)
        string = string + '\n\tmov.b32 %s, %s;' % (name+'.x', name+'_local')
        string = string + '\n\tmov.u32 %s, %s;' % (name+'.y', instrs.tag[type(node.elems[1].n).__name__])
        return string

    def visit_LoadParam(self, node):
        reg = visit(self, node.reg)
        param = visit(self, node.param)
        return '\n\tld.param.u64 %s, [%s];' % (reg, param)

    def visit_MoveInstr(self, node):
        return '\n\tmov.%s%s %s, %s;' % (node.type, node.vect, visit(self, node.lhs), visit(self, node.rhs))

    def visit_BinOpExpr(self, node):
        dest = visit(self, node.dest)
        right = visit(self, node.right)
        left = visit(self, node.left)
        op = ''
        if isinstance(node.op, ast.Add):
            op = 'add'
        elif isinstance(node.op, ast.Sub):
            op = 'sub'
        elif isinstance(node.op, ast.Mult) and (node.type == 'u32' or node.type == 's32'):
            op = 'mul.lo'
        elif isinstance(node.op, ast.Mult) and node.type == 'f32':
            op = 'mul'
        elif isinstance(node.op, ast.Div) and (node.type == 'u32' or node.type == 's32'):
            op = 'div'
            s = '\n\tmov.b32 divhelp0, %s;'%dest+\
                '\n\tmov.b32 divhelp1, %s;'%left+\
                '\n\tmov.b32 divhelp2, %s;'%right+\
                '\n\t%s.%s %s, %s, %s;' % (op, node.type, 'divhelp0', 'divhelp1', 'divhelp2')+\
                '\n\tmov.b32 %s, divhelp0;' % (dest)
            return s
        elif isinstance(node.op, ast.Div) and node.type == 'f32':
            op = 'div.rn'
            s = '\n\tmov.b32 divhelp0, %s;'%dest+\
                '\n\tmov.b32 divhelp1, %s;'%left+\
                '\n\tmov.b32 divhelp2, %s;'%right+\
                '\n\t%s.%s %s, %s, %s;' % (op, node.type, 'divhelp0', 'divhelp1', 'divhelp2')+\
                '\n\tmov.b32 %s, divhelp0;' % (dest)
            return s
        else:
            raise Exception('Binary operation %s not supported' % type(node.op).__name__)
        return '\n\t%s.%s %s, %s, %s;' % (op, node.type, dest, left, right)

    def visit_OrInstr(self, node):
        return '\n\tor.b32 %s, %s, %s;' % (visit(self, node.dest), visit(self, node.lhs), visit(self, node.rhs))

    def visit_AndInstr(self, node):
        return '\n\tand.b32 %s, %s, %s;' % (visit(self, node.dest), visit(self, node.lhs), visit(self, node.rhs))

    def visit_NotInstr(self, node):
        lhs = visit(self, node.lhs)
        return '\n\tnot.b32 %s, %s;' % (lhs, lhs)

    def visit_PredicateBranchInstr(self, node):
        label = visit(self, node.label)
        pred_name = visit(self, node.pred_name)
        pred = ''
        if node.pred:
            pred = '@' + pred_name
        else:
            pred = '@!' + pred_name
        return '\n%s\tbra.uni %s;' % (pred, label)

    def visit_ReturnInstr(self, node):
        return '\n\tret.uni;'

    def visit_CallInstr(self, node):
        args = ''
        for i in range(len(node.args)):
            args = args + visit(self, node.args[i])
            if i < len(node.args)-1:
                args = args + ', '
        if node.lhs:
            lhs = visit(self, node.lhs)
            return '\n\tcall.uni (%s), %s, (%s);' % (lhs, node.funcname, args)
        else:
            return '\n\tcall.uni %s, (%s);' % (node.funcname, args)

    def visit_Num(self, node):
        if isinstance(node.n, int):
            return '%d' % node.n
        elif isinstance(node.n, float):
            return '%f' % node.n
        else:
            raise Exception('Unknown num type, only int and float allowed')

    def visit_Index(self, node):
        val = visit(self, node.value)
        val = int(val)*4
        return val

    def visit_Name(self, node):
        if node.id[0] != '%' and not self.varlist.has_key(node.id):
            self.varlist[node.id] = 'b32'
        return '%s' % node.id

    def visit_Register(self, node):
        if node.id[0] != '%' and not self.varlist.has_key(node.id):
            self.varlist[node.id] = 'b' + str(node.bits)
        return '%s' % node.id

    def visit_Typ(self, node):
        s = visit(self, node.value)
        if isinstance(node.value, ast.Name) or isinstance(node.value, Register):
            return '%s.y' % s
        else:
            return '%s' % s

    def visit_Val(self, node):
        s = visit(self, node.value)
        if isinstance(node.value, ast.Name) or isinstance(node.value, Register):
            return '%s.x' % s
        else:
            return '%s' % s

    def visit_Label(self, node):
        return '\n%s:' % node.label

    def visit_Eq(self, node):
        return 'eq'

    def visit_Gt(self, node):
        return 'gt'

    def visit_Lt(self, node):
        return 'lt'

    def visit_ShiftLeftInstr(self, node):
        return '\n\tshl.b32 %s, %s, %s;' % (visit(self, node.dest), visit(self, node.lhs), visit(self, node.rhs))
                                        
    def visit_ShiftRightInstr(self, node):
        return '\n\tshr.b32 %s, %s, %s;' % (visit(self, node.dest), visit(self, node.lhs), visit(self, node.rhs))

    def visit_SetInstr(self, node):
        return '\n\tset.%s.%s.%s %s, %s, %s;' % (visit(self, node.op), node.type, node.type, visit(self, node.lhs), visit(self, node.left), visit(self, node.right))

    def visit_SetpInstr(self, node):
        pred = visit(self, node.pred)
        return '\n\tsetp.%s.u32 %s, %s, %s;' % (visit(self, node.op), pred, visit(self, node.left), visit(self, node.right))

    def visit_LoadGlobalInstr(self, node):
        lhs = visit(self, node.lhs)
        rhs = visit(self, node.rhs)
        return '\n\tld.global.b32 %s.x, [%s+%s];\n\tmov.b32 %s.y, %s.y;' % (lhs, rhs, visit(self, node.offset), lhs, rhs)


