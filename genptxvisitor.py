import ast
import instrs
import time

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
#        mul.lo.u32 seed, seed, %t_id;\n\
#        mul.wide.u32 localtmp, 1664525, seed;\n\
#        add.u64 localtmp, localtmp, 1013904223;\n\
#        rem.u64 localtmp, localtmp, 4294967296;\n\
#        cvt.u32.u64 seed, localtmp;\n\
#        cvt.rn.f32.u64 rval.x, localtmp;\n\
#        div.approx.f32 rval.x, rval.x, 4294967296.0;\n\
#        mov.u32 rval.y, 2;\n\
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
#  return conv*(i-1);
#}

    def visit_Module(self, node):
        stmts = ''
        preamble = '\n.version 2.0\n.target sm_20\n'
        self.funcs = '\
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
        mul.f32 rval, 4.65661287e-10, tmp0;\n\
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
}'
#.func (.reg .v2 .b32 rval) range (.reg .v2 .s32 length){\n\
#        .reg .pred run;\n\
#        .reg .u32 pos;\n\
#        .reg .v2 .b32 elem;\n\
#        mov.u32 elem.y, 2;\n\
#//        mov.f32 elem.x, 2.0;\n\
#        .local .v2 .b32 arr[7001];\n\
#        .reg .u32 list;\n\
#        mov.u32 list, arr;\n\
#        st.local.v2.u32 [list], length;\n\
#        mul.lo.u32 pos, length.x, 8;\n\
#        add.u32 list, list, pos;\n\
#        cvt.rn.f32.s32 elem.x, length.x;\n\
#start:\n\
#        setp.gt.s32 run, length.x, -1;\n\
#  @!run bra end;\n\
#        st.local.v2.f32 [list], elem;\n\
#        sub.u32 list, list, 8;\n\
#        sub.s32 length.x, length.x, 1;\n\
#        sub.f32 elem.x, elem.x, 1.0;\n\
#        bra start;\n\
#end:\n\
#}\n\
        for i in node.body:
            meth = getattr(self, 'visit_'+type(i).__name__)
            stmts = stmts + meth(i)
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
#                else:
 #                   stmts = "\n.regparam .v2 .b32 %s;" % node.args.args[i].id + stmts
            for i in node.body:
                meth = getattr(self, 'visit_'+type(i).__name__)
                stmts = stmts + meth(i)
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
\tmov.u32 seed, '+ str(int(time.time()*1000)) +';\n' + stmts
            #TEMP!!
            stmts = '\n\t.reg .v2 .b32 %tmp<'+str(instrs.tmpcounter)+'>;' + stmts
#            stmts = "\n\t.reg .v2 .b32 %letify<500>;" + stmts
            stmts = '\n\t.reg .pred %pred<'+str(instrs.predcounter)+'>;'  + stmts
#            stmts = "\n\t.reg .v2 .b32 %list<500>;" + stmts
            return '\n.entry %s (%s){%s\n}' % (node.name, args, stmts)
        else:
            for i in range(len(node.args.args)):
                args = args + '\n\t.reg .v2 .b32 ' + node.args.args[i].id
                self.varlist[node.args.args[i].id] = 'b32'
                if i < len(node.args.args)-1:
                    args = args + ','
            body = ''
            for i in node.body:
                meth = getattr(self, 'visit_'+type(i).__name__)
                body = body + meth(i)
            self.funcs = self.funcs + '\n.func (%s) %s (%s){' % ('.reg .v2 .b32 %rval', node.name, args)
            #for i in self.varlist:
             #   stmts = '\n\t.reg .v2 .%s %s;' % (self.varlist[i], i) + stmts
            self.var_list = old_varlist
            #TEMP!!
            stmts = stmts + '\n.reg .v2 .b32 %tmp<'+str(instrs.tmpcounter)+'>;'
#            stmts = stmts + "\n.reg .v2 .b32 %letify<500>;"
            stmts = stmts + '\n.reg .pred %pred<'+str(instrs.predcounter)+'>;'
            self.funcs = self.funcs +stmts+ body +'\n}'
            return ''

#    def visit_DeclareArray(self, node):
#        print "GenPTX: DeclareArray", node.name, node.size
#        name = getattr(self, 'visit_'+type(node.name).__name__)(node.name)
#        string = '\n\t.local .v2 .b32 %s[%s];' % (name+'_local', node.size)
#        string = string + '\n\tmov.b32 %s, %s;' % (name+'.x', name+'_local')
#        return string

    def visit_DeclareArray(self, node):
        name = getattr(self, 'visit_'+type(node.name).__name__)(node.name)
        if isinstance(node.elems[1].n, float):
            typ = '.f32'
            l = float(node.elems[0].n)
        elif isinstance(node.elems[1].n, int):
            typ = '.s32'
            l = int(node.elems[0].n)
        else:
            raise Exception ('Unsupported element type in list %s' % node.name.id)

        elems = '{'+str(l)
        for i in node.elems[1:]:
            elems = elems + ', '+str(i.n)
#            typ = typ + ', ' +str(instrs.tag[i])
        elems = elems +'}'
        string = '\n\t.global %s %s[%s] = %s;' % (typ, name+'_local', len(node.elems), elems)
#        string = string + '\n\t.reg .u32 %s;' % (name+'_local_t')
        string = string + '\n\tmov.b32 %s, %s;' % (name+'.x', name+'_local')
        string = string + '\n\tmov.u32 %s, %s;' % (name+'.y', instrs.tag[type(node.elems[1].n).__name__])
        return string

    def visit_LoadParam(self, node):
        reg = getattr(self, 'visit_'+type(node.reg).__name__)(node.reg)
        param = getattr(self, 'visit_'+type(node.param).__name__)(node.param)
        return '\n\tld.param.u64 %s, [%s];' % (reg, param)

    def visit_MoveInstr(self, node):
        rhs_meth = getattr(self, 'visit_'+type(node.rhs).__name__)
        lhs_meth = getattr(self, 'visit_'+type(node.lhs).__name__)
        return '\n\tmov.%s%s %s, %s;' % (node.type, node.vect, lhs_meth(node.lhs), rhs_meth(node.rhs))

    def visit_BinOpExpr(self, node):
        dest = getattr(self, 'visit_'+type(node.dest).__name__)(node.dest)
        right = getattr(self, 'visit_'+type(node.right).__name__)(node.right)
        left = getattr(self, 'visit_'+type(node.left).__name__)(node.left)
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
        dest_meth = getattr(self, 'visit_'+type(node.dest).__name__)
        lhs_meth = getattr(self, 'visit_'+type(node.lhs).__name__)
        rhs_meth = getattr(self, 'visit_'+type(node.rhs).__name__)
        return '\n\tor.b32 %s, %s, %s;' % (dest_meth(node.dest), lhs_meth(node.lhs), rhs_meth(node.rhs))

    def visit_AndInstr(self, node):
        dest_meth = getattr(self, 'visit_'+type(node.dest).__name__)
        lhs_meth = getattr(self, 'visit_'+type(node.lhs).__name__)
        rhs_meth = getattr(self, 'visit_'+type(node.rhs).__name__)
        return '\n\tand.b32 %s, %s, %s;' % (dest_meth(node.dest), lhs_meth(node.lhs), rhs_meth(node.rhs))

    def visit_NotInstr(self, node):
        lhs = getattr(self, 'visit_'+type(node.lhs).__name__)(node.lhs)
        return '\n\tnot.b32 %s, %s;' % (lhs, lhs)

    def visit_PredicateBranchInstr(self, node):
        label = getattr(self, 'visit_'+type(node.label).__name__)(node.label)
        pred_name = getattr(self, 'visit_'+type(node.pred_name).__name__)(node.pred_name)
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
            meth = getattr(self, 'visit_'+type(node.args[i]).__name__)
            args = args + meth(node.args[i])
            if i < len(node.args)-1:
                args = args + ', '
        if node.lhs:
            lhs = getattr(self, 'visit_'+type(node.lhs).__name__)(node.lhs)
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
        val = getattr(self, 'visit_'+type(node.value).__name__)(node.value)
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
        s = getattr(self, 'visit_'+type(node.value).__name__)(node.value)
        if isinstance(node.value, ast.Name) or isinstance(node.value, instrs.Register):
            return '%s.y' % s
        else:
            return '%s' % s

    def visit_Val(self, node):
        s = getattr(self, 'visit_'+type(node.value).__name__)(node.value)
        if isinstance(node.value, ast.Name) or isinstance(node.value, instrs.Register):
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
        dest_meth = getattr(self, 'visit_'+type(node.dest).__name__)
        lhs_meth = getattr(self, 'visit_'+type(node.lhs).__name__)
        rhs_meth = getattr(self, 'visit_'+type(node.rhs).__name__)
        return '\n\tshl.b32 %s, %s, %s;' % (dest_meth(node.dest), lhs_meth(node.lhs), rhs_meth(node.rhs))
                                        
    def visit_ShiftRightInstr(self, node):
        dest_meth = getattr(self, 'visit_'+type(node.dest).__name__)
        lhs_meth = getattr(self, 'visit_'+type(node.lhs).__name__)
        rhs_meth = getattr(self, 'visit_'+type(node.rhs).__name__)
        return '\n\tshr.b32 %s, %s, %s;' % (dest_meth(node.dest), lhs_meth(node.lhs), rhs_meth(node.rhs))

    def visit_SetInstr(self, node):
        lhs_meth = getattr(self, 'visit_'+type(node.lhs).__name__)
        left_meth = getattr(self, 'visit_'+type(node.left).__name__)
        right_meth = getattr(self, 'visit_'+type(node.right).__name__)
        op_name = getattr(self, 'visit_'+ type(node.op).__name__)
        return '\n\tset.%s.%s.%s %s, %s, %s;' % (op_name(node.op), node.type, node.type, lhs_meth(node.lhs), left_meth(node.left), right_meth(node.right))

    def visit_SetpInstr(self, node):
        pred = getattr(self, 'visit_'+type(node.pred).__name__)(node.pred)
        left_meth = getattr(self, 'visit_'+type(node.left).__name__)
        right_meth = getattr(self, 'visit_'+type(node.right).__name__)
        op_name = getattr(self, 'visit_'+ node.op.__name__)
        return '\n\tsetp.%s.u32 %s, %s, %s;' % (op_name(node.op), pred, left_meth(node.left), right_meth(node.right))

    def visit_LoadGlobalInstr(self, node):
        lhs = getattr(self, 'visit_'+type(node.lhs).__name__)(node.lhs)
        rhs = getattr(self, 'visit_'+type(node.rhs).__name__)(node.rhs)
        offset = getattr(self, 'visit_'+type(node.offset).__name__)(node.offset)
        return '\n\tld.global.b32 %s.x, [%s+%s];\n\tmov.b32 %s.y, %s.y;' % (lhs, rhs, offset, lhs, rhs)

#    def visit_StoreLocalInstr(self, node):
#        lhs = getattr(self, 'visit_'+type(node.lhs).__name__)(node.lhs)
#        rhs = getattr(self, 'visit_'+type(node.rhs).__name__)(node.rhs)
#        offset = getattr(self, 'visit_'+type(node.offset).__name__)(node.offset)
#        return '\n\tst.local.v2.b32 [%s+%s], %s;' % (lhs, offset, rhs)
