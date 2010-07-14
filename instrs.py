import ast
import instrs

tmpcounter = 0
labelcounter = 0
predcounter = 0

def generate_var(varname):
    global tmpcounter
    global labelcounter
    global predcounter

    if varname == 'tmp':
        name = '%'+ varname + str(tmpcounter)
        tmpcounter = tmpcounter + 1
#        varlist[name] = 32
    elif varname == 'label':
        name = '%'+ varname + str(labelcounter)
        labelcounter = labelcounter + 1
        #varlist[name] = 32
    elif varname == 'pred':
        name = '%'+ varname + str(predcounter)
        predcounter = predcounter + 1
#        predlist.append(name)
    else:
        raise Exception('Variable %s not allowed' % varname)
    return name

def letify(expr, k):
    if isinstance(expr, ast.Name) or isinstance(expr, ast.Num):
        return k(expr)
    else:
        n = generate_var("tmp")
        return instrs.Let(n, expr, k(ast.Name(n, ast.Load())))

def visit(env, *args):
    return getattr(env, 'visit_'+type(args[0]).__name__)(*args)

def set_list(lhs, typ, size):
    if isinstance(lhs, ast.Name):
        lists[lhs.id] = (typ, size)
    else:
        raise Exception ('Unknown lhs in set_list')

def get_list(lhs):
    if isinstance(lhs, ast.Name):
        return lists[lhs.id]
    else:
        raise Exception ('Unknown lhs in get_list')

#var_types = dict()
#lists = dict()
#channel_args = dict()
#return_vars = dict()
entryFunc = None
#args = []
#randomused = False
#ext_funcs = ''
varlist = {}
colornames = {}
predlist = []
reserved_registers = []
builtin_functions = ['range', 'reduce']
shift = { 'int' : 2, 'bool' : 2, 'float': 2, 'big' : 2 }
tag = { 'int' : 0, 'bool' : 1, 'float': 2, 'big' : 3 }
mask = 3

class MoveInstr(ast.AST):
    def __init__(self, lhs, rhs, vect, typ):
        self.lhs = lhs
        self.rhs = rhs
        self.vect = vect
        self.type = typ
        self._fields = ('lhs', 'rhs')

class AddInstr(ast.AST):
    def __init__(self, dest, lhs, rhs, typ):
        self.dest = dest
        self.lhs = lhs
        self.rhs = rhs
        self.type = typ
        self._fields = ('lhs', 'rhs')

class MultInstr(ast.AST):
    def __init__(self, dest, lhs, rhs, typ):
        self.dest = dest
        self.lhs = lhs
        self.rhs = rhs
        self.type = typ
        self._fields = ('lhs', 'rhs')

class DivInstr(ast.AST):
    def __init__(self, dest, lhs, rhs, typ):
        self.dest = dest
        self.lhs = lhs
        self.rhs = rhs
        self.type = typ
        self._fields = ('lhs', 'rhs')

#class IntAdressMultInstr(ast.AST):
#    def __init__(self, dest, lhs, rhs):
#        self.dest = dest
#        self.lhs = lhs
#        self.rhs = rhs
#        self._fields = ('lhs', 'rhs')

class USubInstr(ast.AST):
    def __init__(self, lhs, rhs, typ):
        self.lhs = lhs
        self.rhs = rhs
        self.type = typ
        self._fields = ('lhs', 'rhs')

class LoadGlobalInstr(ast.AST):
    def __init__(self, lhs, rhs, offset):
        self.lhs = lhs
        self.rhs = rhs
        self.offset = offset
        self._fields = ('lhs', 'rhs', 'offset')

class StoreLocalInstr(ast.AST):
    def __init__(self, lhs, rhs, offset):
        self.lhs = lhs
        self.rhs = rhs
        self.offset = offset
        self._fields = ('lhs', 'rhs', 'offset')

class AndInstr(ast.AST):
    def __init__(self, dest, lhs, rhs):
        self.dest = dest
        self.lhs = lhs
        self.rhs = rhs
        self._fields = ('dest', 'lhs', 'rhs')

class ReturnInstr(ast.AST):
    def __init__(self):
        pass

class SetInstr(ast.AST):
    def __init__(self, lhs, left, op, right, typ):
        self.lhs = lhs
        self.left = left
        self.op = op
        self.right = right
        self.type = typ
        self._fields = ('lhs', 'left', 'op', 'right')

class SetpInstr(ast.AST):
    def __init__(self, pred, left, op, right):
        self.pred = pred
        self.left = left
        self.op = op
        self.right = right
        self._fields = ('pred', 'left', 'op', 'right')

class CallInstr(ast.AST):
    def __init__(self, lhs, funcname, args):
        self.lhs = lhs
        self.funcname = funcname
        self.args = args
        self._fields = ('lhs', 'funcname', 'args')

class PredicateBranchInstr(ast.AST):
    def __init__(self, pred_name, label, pred):
        self.pred_name = pred_name
        self.label = label
        self.pred = pred
        self._fields = ('pred_name', 'label')

class Compare(ast.AST):
    def __init__(self, left, op, right, typ):
        self.left = left
        self.op = op
        self.right = right
        self.type = typ
        self._fields = ('lhs', 'op', 'rhs')

class BinOp(ast.AST):
    def __init__(self, left, op, right, typ):
        self.left = left
        self.op = op
        self.right = right
        self.type = typ
        self._fields = ('lhs', 'op', 'rhs')

class BinOpExpr(ast.AST):
    def __init__(self, dest, left, op, right, typ):
        self.dest = dest
        self.left = left
        self.op = op
        self.right = right
        self.type = typ
        self._fields = ('lhs', 'op', 'rhs')

class Label(ast.AST):
    def __init__(self, label):
        self.label = label
        self._fields = ('label')

class Typ(ast.AST):
    def __init__(self, value):
        self.value = value
        self._fields = ('value')

class Val(ast.AST):
    def __init__(self, value):
        self.value = value
        self._fields = ('value')

#class EntryFunctionDef(ast.AST):
#    def __init__(self, name, args, body, decorator_list):
#        self.name = name
#        self.args = args
#        self.body = body
#        self.decorator_list = decorator_list
#        self._fields = ('name', 'args', 'body', 'decorator_list')

#class ImmAddress(ast.AST):
#    def __init__(self, val):
#        self.n = val
#        self._fields = ('val')

#class Address(ast.AST):
#    def __init__(self, name):
#        self.id = name
#        self._fields = ('id')

class ShiftLeftInstr(ast.AST):
    def __init__(self, dest, lhs, rhs):
        self.dest = dest
        self.lhs = lhs
        self.rhs = rhs
        self._fields = ('dest', 'lhs', 'rhs')

class ShiftRightInstr(ast.AST):
    def __init__(self, dest, lhs, rhs):
        self.dest = dest
        self.lhs = lhs
        self.rhs = rhs
        self._fields = ('dest', 'lhs', 'rhs')

#class SetpNeqInstr(ast.AST):
#    def __init__(self, pred, testa, testb):
#        self.pred = pred
#        self.testa = testa
#        self.testb = testb
#        self._fields = ('pred', 'testa', 'testb')

#class SelpInstr(ast.AST):
#    def __init__(self, res, body, orelse, pred):
#        self.res = res
#        self.body = body
#        self.orelse = orelse
#        self.pred = pred
#        self._fields = ('res', 'body', 'orelse', 'pred')


class Register(ast.AST):
    def __init__(self, name, bits):
        self.id = name
        self.bits = bits
        self._fields = ('id')

class SetSubscript(ast.AST):
    def __init__(self, container, val, key):
        self.container = container
        self.val = val
        self.key = key
        self._fields = ('container', 'key', 'val')

class SetType(ast.AST):
    def __init__(self, typ, arg):
        self.typ = typ
        self.arg = arg
        self._fields = ('typ', 'arg')
    def __repr__(self):
        return "SetType(%s, %s)" % (self.typ, repr(self.arg))

class GetType(ast.AST):
    def __init__(self, typ, arg):
        self.typ = typ
        self.arg = arg
        self._fields = ('typ', 'arg')
    def __repr__(self):
        return "GetType(%s, %s)" % (self.typ, repr(self.arg))

class Let(ast.AST):
    def __init__(self, var, rhs, body):
        self.var = var
        self.rhs = rhs
        self.body = body
        self._fields = ('var', 'rhs', 'body')
    def __repr__(self):
        return "Let(%s, %s, %s)" % (self.var, repr(self.rhs), repr(self.body))

#class GetTag(ast.AST):
#    def __init__(self, arg):
#        self.arg = arg
#        self._fields = ('arg')
#    def __repr__(self):
#        return "GetTag(%s)" % repr(self.arg)

#class DeclareArray(ast.AST):
#    def __init__(self, name, size):
#        self.name = name
#        self.size = size
#        self._fields = ('name', 'size')

class DeclareArray(ast.AST):
    def __init__(self, name, elems):
        self.name = name
        self.elems = elems
        self._fields = ('name', 'size')

#class DeclareGlobal(ast.AST):
#    def __init__(self, name):
#        self.name = name
#        self._fields = ('name')

class LoadParam(ast.AST):
    def __init__(self, reg, param):
        self.reg = reg
        self.param = param
        self._fields = ('reg', 'param')

