import ast
import instrs

#######################################
### Instrs                          ###
### Helper functions and variables, ###
### as well as node definitions     ###
#######################################

#Counter to keep track of the number of variables to generate
tmpcounter = 0
labelcounter = 0
predcounter = 0

#entryFunc is set when entry function is determined
entryFunc = None

#Define builtin-functions
builtin_functions = {'range':False, 'reduce':False, 'random':False, 'float':False, 'int':False}

#Set bits used in boxing
tag = { 'int' : 0, 'float': 1, 'intlist' : 2, 'floatlist' : 3}

#List of variables in current scope
varlist = {}

#Output count
channel_vars = {}

args = []

threads = 0
#Helper function that generates a new variable
#and returns its name. Type of variable is
#determined by the varname argument
def generate_var(varname):
    global tmpcounter
    global labelcounter
    global predcounter

    if varname == 'tmp':
        name = '%'+ varname + str(tmpcounter)
        tmpcounter = tmpcounter + 1
    elif varname == 'label':
        name = '%'+ varname + str(labelcounter)
        labelcounter = labelcounter + 1
    elif varname == 'pred':
        name = '%'+ varname + str(predcounter)
        predcounter = predcounter + 1
    else:
        raise Exception('Variable %s not allowed' % varname)
    return name

#Generate a let instruction as let n = expr in k(n)
def letify(expr, k):
    if isinstance(expr, ast.Name) or isinstance(expr, ast.Num):
        return k(expr)
    else:
        n = generate_var("tmp")
        return Let(n, expr, k(ast.Name(n, ast.Load())))

#Visit is used in all passes to access visitor functions
def visit(env, *args):
    return getattr(env, 'visit_'+type(args[0]).__name__)(*args)

#######################
## Node definitions ###
#######################
class MoveInstr(ast.AST):
    def __init__(self, lhs, rhs, vect, typ):
        self.lhs = lhs
        self.rhs = rhs
        self.vect = vect
        self.type = typ
        self._fields = ('lhs', 'rhs')

class LoadGlobalInstr(ast.AST):
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
    #A PTX return instr has no arguments
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

#BinOpExpr contains destination register,
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

class SetSubscript(ast.AST):
    def __init__(self, container, value, key):
        self.container = container
        self.value = value
        self.key = key
        self._fields = ('container', 'key', 'value')

class SetSubscriptExpr(ast.AST):
    def __init__(self, lhs, container, value, key):
        self.lhs = lhs
        self.container = container
        self.value = value
        self.key = key
        self._fields = ('container', 'key', 'value')

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

class DeclareArray(ast.AST):
    def __init__(self, name, elems):
        self.name = name
        self.elems = elems
        self._fields = ('name', 'size')

class LoadParam(ast.AST):
    def __init__(self, reg, param):
        self.reg = reg
        self.param = param
        self._fields = ('reg', 'param')

