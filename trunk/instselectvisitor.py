import ast
import instrs

class InstSelectVisitor(ast.NodeVisitor):
    def visit_Module(self, node):
        stmts = []
        for i in node.body:
            meth = getattr(self, 'visit_'+type(i).__name__)
            stmts = stmts + meth(i)
        return ast.Module(stmts)

#    def visit_EntryFunctionDef(self, node):
#        stmts = []
#        #scope_vars = instrs.var_types[node.name]
#        for i in node.body:
#            meth = getattr(self, 'visit_'+type(i).__name__)
#            stmts = stmts + meth(i, node.name)
#        #instrs.var_types[node.name] = scope_vars
#        return [instrs.EntryFunctionDef(node.name, node.args, stmts, node.decorator_list)]

    def visit_FunctionDef(self, node):
        stmts = []
        for i in node.body:
            meth = getattr(self, 'visit_'+type(i).__name__)
            stmts = stmts + meth(i)
        return [ast.FunctionDef(node.name, node.args, stmts, node.decorator_list)]

    def visit_LoadParam(self, node):
        return [node]

    def visit_Expr(self, node):
        expr_meth = getattr(self, 'visit_'+type(node.value).__name__)
        return expr_meth(node.value, None)
        
    def visit_Assign(self, node):
        lhs = node.targets[0].id
        meth = getattr(self, 'visit_'+type(node.value).__name__)
        return meth(node.value, lhs)

    def visit_Return(self, node):
        return [instrs.MoveInstr(instrs.Val(ast.Name('%rval', ast.Load())), instrs.Val(node.value), '', 'b32'),
                instrs.MoveInstr(instrs.Typ(ast.Name('%rval', ast.Load())), instrs.Typ(node.value), '', 's32'),
                instrs.ReturnInstr()]

    def visit_If(self, node):
        thens = []
        orelses = []
        for i in node.body:
            thens = thens + getattr(self, 'visit_'+type(i).__name__)(i)
        for i in node.orelse:
            orelses = orelses + getattr(self, 'visit_'+type(i).__name__)(i)
        orelse_label = instrs.generate_var("label")
        end_label = instrs.generate_var("label")
        pred = instrs.generate_var("pred")
        return [instrs.SetpInstr(ast.Name(pred, ast.Store()), instrs.Val(node.test), ast.Gt, ast.Num(0)),\
                instrs.PredicateBranchInstr(ast.Name(pred, ast.Store()), ast.Name(orelse_label, ast.Load()), False)] + thens +\
               [instrs.PredicateBranchInstr(ast.Name(pred, ast.Store()), ast.Name(end_label, ast.Load()), True), instrs.Label(orelse_label)]+\
                orelses + [instrs.Label(end_label)]

#    def visit_For(self, node):
#        bodys = []
#        orelses = []
#        for i in node.body:
#            bodys = bodys + getattr(self, 'visit_'+type(i).__name__)(i)
#        for i in node.orelse:
#            orelses = orelses + getattr(self, 'visit_'+type(i).__name__)(i)
#        stmts = []
#        print node.target.id, node.iter
#        for node.target.id in node.iter:
#            print "HEP"

    def visit_SetSubscript(self, node):
        return [instrs.StoreLocalInstr(node.container, node.val, node.key)]

    def visit_DeclareArray(self, node):
        return [node]
         
    def visit_InjectFrom(self, node, lhs):
        if node.typ == 'big':
            movetype = 'u32'
        elif node.typ == 'int' or node.typ == 'bool':
            movetype = 's32'
        elif node.typ == 'float':
            movetype = 'f32'
        return [instrs.MoveInstr(instrs.Typ(ast.Name(lhs, ast.Store())), ast.Num(instrs.tag[node.typ]), '', 'u32'),
                instrs.MoveInstr(instrs.Val(ast.Name(lhs, ast.Store())), instrs.Val(node.arg), '', movetype)]
#        if node.typ == 'big':
#            return [#instrs.MoveInstr(ast.Name(lhs, ast.Store()), node.arg, 'u32'),
#                    instrs.OrInstr(ast.Name(lhs, ast.Load()), node.arg, ast.Num(instrs.tag['big']))]
#        elif node.typ == 'int':
#                    #instrs.MoveInstr(ast.Name(lhs, ast.Store()), node.arg, 's32'),
#            return [instrs.ShiftLeftInstr(ast.Name(lhs, ast.Load()), node.arg, ast.Num(instrs.shift[node.typ])),
#                    instrs.OrInstr(ast.Name(lhs, ast.Load()), ast.Name(lhs, ast.Load()), ast.Num(instrs.tag[node.typ]))]
#        elif node.typ == 'float':
#                   #instrs.MoveInstr(ast.Name(lhs, ast.Load()), node.arg, 'f32'),
#            return [instrs.ShiftLeftInstr(ast.Name(lhs, ast.Load()), node.arg, ast.Num(instrs.shift[node.typ])),
#                    instrs.OrInstr(ast.Name(lhs, ast.Load()), ast.Name(lhs, ast.Load()), ast.Num(instrs.tag[node.typ]))]

    def visit_ProjectTo(self, node, lhs):
        if node.typ == 'big':
            movetype = 'u64'
        elif node.typ == 'int' or node.typ == 'bool':
            movetype = 's32'
        elif node.typ == 'float':
            movetype = 'f32'
        return [instrs.MoveInstr(instrs.Val(ast.Name(lhs, ast.Store())), instrs.Val(node.arg), '', movetype)]
#        if node.typ == 'big':
#            return [instrs.MoveInstr(ast.Name(lhs, ast.Store()), ast.Num(instrs.mask), 'u64'),
#                    instrs.NotInstr(ast.Name(lhs, ast.Store())),
#                    instrs.AndInstr(ast.Name(lhs, ast.Store()), ast.Name(lhs, ast.Store()), node.arg)]
#        else:
#                #instrs.MoveInstr(ast.Name(lhs, ast.Store()), node.arg, 's32'),
#            return [instrs.ShiftRightInstr(ast.Name(lhs, ast.Store()), node.arg, ast.Num(instrs.shift[node.typ]))]
#
##        elif node.typ == 'float':
##            return [instrs.MoveInstr(ast.Name(lhs, ast.Store()), node.arg, 'f32'),
##                    instrs.ShiftRightInstr(ast.Name(lhs, ast.Store()), ast.Num(instrs.shift[node.typ]))]

    def visit_Lambda(self, node, lhs):
        stmts = []
        for i in node.body:
            meth = getattr(self, 'visit_'+type(i).__name__)
            stmts = stmts + meth(i)
        return [ast.FunctionDef(lhs, node.args, stmts, [])]
        
    def visit_BinOp(self, node, lhs):
        if isinstance(node.op, ast.Pow):
            start = instrs.generate_var('label')
            end = instrs.generate_var('label')
            pred = instrs.generate_var('pred')
            if node.type == 'f32':
                one = 1.0
            else:
                one = 1
            return [instrs.MoveInstr(instrs.Val(ast.Name(lhs, ast.Store())), ast.Num(one), '', node.type), #lhs = 1
                    instrs.Label(start), #start:
                    instrs.SetpInstr(ast.Name(pred, ast.Store()), instrs.Val(node.right), ast.Eq, ast.Num(0)), 
                    instrs.PredicateBranchInstr(ast.Name(pred, ast.Store()), ast.Name(end, ast.Store()), True), # if right == 0, bra end
                    instrs.BinOpExpr(instrs.Val(ast.Name(lhs, ast.Store())), instrs.Val(ast.Name(lhs, ast.Store())), ast.Mult(), instrs.Val(node.left), node.type),  #lhs = lhs * left
                    instrs.BinOpExpr(instrs.Val(node.right), instrs.Val(node.right), ast.Sub(), ast.Num(1), 'u32'), #right = right - 1
                    instrs.PredicateBranchInstr(ast.Name(pred, ast.Store()), ast.Name(start, ast.Store()), False), #bra start
                    instrs.Label(end)] #label end
        else:
            return [instrs.BinOpExpr(instrs.Val(ast.Name(lhs, ast.Store())), node.left, node.op, node.right, node.type)]

    def visit_Num(self, node, lhs):
        typ = type(node.n).__name__
        if typ  == 'int':
            return [instrs.MoveInstr(instrs.Val(ast.Name(lhs, ast.Store())), node, '', 's32')]
        elif typ == 'float':
            return [instrs.MoveInstr(instrs.Val(ast.Name(lhs, ast.Store())), node, '', 'f32')]
        else:
            raise Exception('Unknown type %s' % typ)

    def visit_Name(self, node, lhs):
        if lhs == node.id:
            return []
        else:
            return [instrs.MoveInstr(ast.Name(lhs, ast.Store()), node, '.v2', 'b32')]

    def visit_GetTag(self, node, lhs):
        return [instrs.Typ(node.arg)]

    def visit_Compare(self, node, lhs):
        left = node.left
        op = node.op
        right = node.right
        tag = ''
        if node.type == 'f32':
            tag = instrs.tag['float']
            return [instrs.SetInstr(instrs.Val(ast.Name(lhs, ast.Store())), instrs.Val(left), op, instrs.Val(right), node.type),
                    instrs.MoveInstr(instrs.Typ(ast.Name(lhs, ast.Store())), ast.Num(tag),'', 'u32')]
        elif node.type == 's32' or node.type == 'u32':
            tag = instrs.tag['int']
            #Since ints return 0xFFFFFFFF on true, we need to use an and operation to turn it into the value 1
            return [instrs.SetInstr(instrs.Val(ast.Name(lhs, ast.Store())), instrs.Val(left), op, instrs.Val(right), node.type),
                    instrs.MoveInstr(instrs.Typ(ast.Name(lhs, ast.Store())), ast.Num(tag),'', 'u32'),
                    instrs.AndInstr(instrs.Val(ast.Name(lhs, ast.Store())), instrs.Val(ast.Name(lhs, ast.Store())), ast.Num(1))]
        else:
            raise Exception('Unkown type %s' % node.type)

    def visit_Call(self, node, lhs):
        #If its a call to reduce, remove first argument
        if node.func.id == 'reduce':
            node.args = node.args[1:]
        if lhs is None:
            return [instrs.CallInstr(None, node.func.id, node.args)]
        else:
            return [instrs.CallInstr(ast.Name(lhs, ast.Store()), node.func.id, node.args)]

    def visit_Subscript(self, node, lhs):
        if isinstance(node.slice, ast.Index):
            node.slice.value.n = node.slice.value.n + 1
        else:
            raise Exception('No slicing allowed in array index')
        return [instrs.LoadGlobalInstr(ast.Name(lhs, ast.Store()), node.value, node.slice)]


