import ast
from instrs import *
from random import *
from builtin_defs import *

###################################################
### GenPTXVisitor                               ###
### Input: An AST of PTX instructions           ###
### Output: A syntactically correct PTX string  ###
###                                             ###
### All nodes return a string, containing a PTX ###
### representation of the given node            ###
###################################################
class GenPTXVisitor(ast.NodeVisitor):
    def __init__(self):
        self.varlist = {}
        self.str_lst = []

    ########################
    ### Helper functions ###
    ########################
    def make_ChannelEndRead(self, name, typ):
        func = '\n.reg .b64 __cuda__%s_global;\n\
        .func (.reg .v2 .b32 rval) %s (){\n\
        \tadd.u64 __cuda__%s_global, __cuda__%s_global, %%tid_offset;\n\
        \tld.global.v2.b32 rval, [__cuda__%s_global];\n}\n' % (name, name, name, name, name)
        return func

    def make_ChannelEndWrite(self, name, typ):
        func = '\n.reg .b64 __cuda__%s_global;\n\
        .func () %s (.reg .v2 .b32 val){\n\
        \tadd.u64 __cuda__%s_global, __cuda__%s_global, %%tid_offset;\n\
        \tst.global.v2.b32 [__cuda__%s_global], val;\n}\n' % (name, name, name, name, name)
        return func

#    def make_ChannelEndRead(self, name, typ):
#        func = '\n.reg .b64 __cuda__%s_global;\n\
#        .func (.reg .v2 .b32 rval) %s (){\n\
#        \tadd.u64 __cuda__%s_global, __cuda__%s_global, %%tid_offset;\n\
#        \tld.global.b32 rval.x, [__cuda__%s_global];\n\
#        \tmov.s32 rval.y, %s;\n}\n' % (name, name, name, name, name, instrs.tag[typ])
#        return func

#    def make_ChannelEndWrite(self, name, typ):
#        func = '\n.reg .b64 __cuda__%s_global;\n\
#        .func () %s (.reg .v2 .b32 val){\n\
#        \tst.global.b32 [__cuda__%s_global], val.y;\n\
#        \tadd.u64 __cuda__%s_global, __cuda__%s_global, %%tid_offset;\n\
#        \tst.global.b32 [__cuda__%s_global+4], val.x;\n}\n' % (name, name, name, name, name, name)
#        return func

    def visit_Module(self, node):
        #Append module preamble, as well as global variables
        self.str_lst.append('\
\n.version 2.0\n.target sm_20\n\
.reg .b32 divhelp<3>;\n\
.reg .b64 %tid_offset;\n\
.reg .b64 %tid_offseth;\n\
.reg .b32 %t_id;\n\
.reg .v2 .b32 %seed;\n')

        #Append builtin functions, if used
        for i in builtin_functions:
            if builtin_functions[i]:
                self.str_lst.append(builtin_defs[i])

        #Iterate module body
        body = [visit(self,i) for i in node.body]

        #Join list into a string
        return ''.join(self.str_lst+body)

    def visit_FunctionDef(self, node):
        old_varlist = self.varlist
        definition = []
        args = []
        declarations = []
        body = []

        #Entry function
        if instrs.entryFunc == node.name:
            #Function definition
            definition = ['\n.entry %s(' % node.name]
            
            #Add channel arguments to definition
            definition.append(', '.join(['\n\t.param .u64 __cudaparam__' + node.args.args[i].id for i in range(len(node.args.args)) if instrs.args[i][0] == 'ChannelEndRead' or instrs.args[i][0] == 'ChannelEndWrite']))
            definition.append(')\n{')

            for i in range(len(node.args.args)):
                if instrs.args[i][0] == 'ChannelEndRead':
                    self.str_lst.append(self.make_ChannelEndRead(node.args.args[i].id, instrs.args[i][1]))
                    body.append('\n\tld.param.u64 __cuda__%s_global, [__cudaparam__%s];' % (node.args.args[i].id, node.args.args[i].id))
                if instrs.args[i][0] == 'ChannelEndWrite':
                    self.str_lst.append(self.make_ChannelEndWrite(node.args.args[i].id, instrs.args[i][1]))
                    body.append('\n\tld.param.u64 __cuda__%s_global, [__cudaparam__%s];' % (node.args.args[i].id, node.args.args[i].id))

            #Thread id calculations
            declarations.append('\n\t.reg .b32 %r<3>;\n\
\t.reg .b16 %rh<3>;\n\
\tmov.u16 %rh1, %ctaid.x;\n\
\tmov.u16 %rh2, %ntid.x;\n\
\tmul.wide.u16 %r1, %rh1, %rh2;\n\
\tcvt.u32.u16 %r2, %tid.x;\n\
\tadd.u32 %t_id, %r2, %r1;\n\
\tmul.wide.u32 %tid_offseth, %t_id, 4;\n\
\tmul.wide.u32 %tid_offset, %t_id, 8;\n')
            
            #Random seeding, if used
            if builtin_functions['random']:
                body.append('\n\tadd.u32 %r0, %t_id, ')
                body.append(str(randint(0,4294967295)))
                body.append(';\n\
\tmov.u32 %seed.x, %r0;\n\
\tcall (%seed), random, ();\n\
\tcall (%seed), random, ();\n')

            #Visit body nodes. These build up self.varlist
            body = body + [visit(self,i) for i in node.body]
 
            #Place created varlist in declarations
            for i in self.varlist:
                declarations.append('\n\t.reg .v2 .%s %s;' % (self.varlist[i], i))

            #Revert to previous varlist
            self.varlist = old_varlist

            declarations.append('\n\t.reg .v2 .b32 %tmp<'+str(instrs.tmpcounter)+'>;')
            declarations.append('\n\t.reg .pred %pred<'+str(instrs.predcounter)+'>;')
            body.append('\n}')

            return ''.join(definition + declarations + body)

        #Non-entry function
        else:
            #Function definition
            definition = ['\n.func (.reg .v2 .b32 %%rval) %s' % node.name]

            #Add arguments to definition
            func_args_list = [i.id for i in node.args.args]
            args = ', '.join(['\n\t.reg .v2 .b32 ' + i for i in func_args_list])
            definition.append('(')
            definition.append(args)
            definition.append(')\n{')

            #Traverse body
            body = [visit(self,i) for i in node.body]

            #Place created varlist in declarations
            for i in self.varlist:
                if i not in func_args_list:
                    declarations.append('\n\t.reg .v2 .%s %s;' % (self.varlist[i], i))

            #Revert to previous varlist
            self.varlist = old_varlist
            
            #Add temporaries to declarations
            declarations.append('\n\t.reg .v2 .b32 %tmp<'+str(instrs.tmpcounter)+'>;')
            declarations.append('\n\t.reg .pred %pred<'+str(instrs.predcounter)+'>;')

            #End body
            body.append('\n}')

            #Store to global str_lst, as function defs are not allowed inside function defs
            self.str_lst.append(''.join(definition + declarations + body))
            return ''

    def visit_DeclareArray(self, node):
        name = visit(self, node.name)
        if isinstance(node.elems[1], ast.Num):
            if isinstance(node.elems[1].n, float):
                typ = '.f32'
                l = float(node.elems[0].n)
            elif isinstance(node.elems[1].n, int):
                typ = '.s32'
                l = int(node.elems[0].n)
            else:
                raise Exception ('Unsupported element type in list %s' % node.name.id)
            elems = '{' + str(l) + ', ' + ', '.join([`i.n` for i in node.elems[1:]]) +'}'
            string = '\n\t.global %s %s[%s] = %s;' % (typ, name+'_local', len(node.elems), elems)
            string = string + '\n\tmov.b32 %s, %s;' % (name+'.x', name+'_local')
            string = string + '\n\tmov.u32 %s, %s;' % (name+'.y', instrs.tag[type(node.elems[1].n).__name__])

        elif isinstance(node.elems[1], ast.Name):
            elems = ''.join(['\n\tst.global.%s [%s+%s], %s;' % ('b32', name+'_local',i*4, visit(self, node.elems[i+1])) for i in range(len(node.elems[1:]))])
            string = '\n\t.global.%s %s[%s];' % ('b32', name+'_local', len(node.elems))
            string = string + '\n\tmov.b32 %s, %s;' % (name+'.x', name+'_local')
            string = string + '\n\tmov.u32 %s, %s;' % (name+'.y', node.elems[1]+'.y') + elems
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
            #Divhelp variables are a fix since var1.x / var2.x is currently bugged.
            #Instead we do divhelp1 = var1.x, divhelp2=var2.x, res = divhelp1/divhelp2
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
            raise Exception('Binary operation %s (%s) not supported' % (type(node.op).__name__, node.type))
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
        return '\n%s\tbra %s;' % (pred, label)

    def visit_ReturnInstr(self, node):
        return '\n\tret;'

    def visit_CallInstr(self, node):
        args = ''
        for i in range(len(node.args)):
            args = args + visit(self, node.args[i])
            if i < len(node.args)-1:
                args = args + ', '
        if node.lhs:
            lhs = visit(self, node.lhs)
            return '\n\tcall (%s), %s, (%s);' % (lhs, node.funcname, args)
        else:
            return '\n\tcall %s, (%s);' % (node.funcname, args)

    def visit_Num(self, node):
        if isinstance(node.n, int):
            return '%d' % node.n
        elif isinstance(node.n, float):
            return '%f' % node.n
        else:
            raise Exception('Unknown num type, only int and float allowed')

    def visit_Index(self, node):
        val = visit(self, node.value)
        ##Value is multiplied by 4 to transform to 32 bit offset
        val = int(val)*4
        return val

    def visit_Name(self, node):
        if node.id[0] != '%' and not self.varlist.has_key(node.id):
            self.varlist[node.id] = 'b32'
        return '%s' % node.id

    def visit_Typ(self, node):
        s = visit(self, node.value)
        if isinstance(node.value, ast.Name):
            return '%s.y' % s
        else:
            return '%s' % s

    def visit_Val(self, node):
        s = visit(self, node.value)
        if isinstance(node.value, ast.Name):
            return '%s.x' % s
        else:
            return '%s' % s

    def visit_Label(self, node):
        return '\n%s:' % node.label

    def visit_Eq(self, node):
        return 'eq'

    def visit_NotEq(self, node):
        return 'ne'

    def visit_Lt(self, node):
        return 'lt'

    def visit_LtE(self, node):
        return 'le'

    def visit_Gt(self, node):
        return 'gt'

    def visit_GtE(self, node):
        return 'ge'

    def visit_SetInstr(self, node):
        return '\n\tset.%s.%s.%s %s, %s, %s;' % (visit(self, node.op), node.type, node.type, visit(self, node.lhs), visit(self, node.left), visit(self, node.right))

    def visit_SetpInstr(self, node):
        pred = visit(self, node.pred)
        return '\n\tsetp.%s.u32 %s, %s, %s;' % (visit(self, node.op), pred, visit(self, node.left), visit(self, node.right))

    def visit_SetSubscriptExpr(self, node):
        container = visit(self, node.container)
        key = visit(self, node.key)
        value = visit(self, node.value)
        lhs = visit(self, node.lhs)
        return '\n\tst.global.b32 [%s], %s.x;' % (lhs, value)

    def visit_LoadGlobalInstr(self, node):
        lhs = visit(self, node.lhs)
        rhs = visit(self, node.rhs)
        return '\n\tld.global.b32 %s.x, [%s+%s];\n\tmov.b32 %s.y, %s.y;' % (lhs, rhs, visit(self, node.offset), lhs, rhs)


