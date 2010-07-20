import ast
from instrs import *

##################################################
### InstSelectVisitor                          ###
### Input: A flattened AST with explicit types ###
### Output: An AST of PTX instructions         ###
###                                            ###
### All nodes return a list of nodes           ###
##################################################
class InstSelectVisitor(ast.NodeVisitor):
    def visit_Module(self, node):
        stmts = reduce(list.__add__, [visit(self, i) for i in node.body])
        return ast.Module(stmts)

    ##################
    ### Statements ###
    ##################
    def visit_Assign(self, node):
        lhs = node.targets[0].id
        return visit(self, node.value, lhs)

    def visit_BinOp(self, node, lhs):
        #Power operation
        if isinstance(node.op, ast.Pow):
            #Generate labels for branches
            start = generate_var('label')
            end = generate_var('label')
            pred = generate_var('pred')
            #As lhs must start as the value one, a fix is made to ensure type compatibilty
            if node.type == 'f32': one = 1.0
            else: one = 1
            return [MoveInstr(Val(ast.Name(lhs, ast.Store())), ast.Num(one), '', node.type), #lhs = 1
                    Label(start), #start:
                    SetpInstr(ast.Name(pred, ast.Store()), Val(node.right), ast.Eq(), ast.Num(0)), 
                    PredicateBranchInstr(ast.Name(pred, ast.Store()), ast.Name(end, ast.Store()), True), # if right == 0, bra end
                    BinOpExpr(Val(ast.Name(lhs, ast.Store())), Val(ast.Name(lhs, ast.Store())), ast.Mult(), Val(node.left), node.type),  #lhs = lhs * left
                    BinOpExpr(Val(node.right), Val(node.right), ast.Sub(), ast.Num(1), 'u32'), #right = right - 1
                    PredicateBranchInstr(ast.Name(pred, ast.Store()), ast.Name(start, ast.Store()), False), #bra start
                    Label(end)] #label end
        #All other binary operations
        else:
            return [BinOpExpr(Val(ast.Name(lhs, ast.Store())), node.left, node.op, node.right, node.type)]

    def visit_Call(self, node, lhs):
        #If its a call to reduce, remove first argument, as 
        #its the function is stored in "lambda". Its a fix
        #as indirect calls are not allowed in PTX 2.0
        if node.func.id == 'reduce':
            node.args = node.args[1:]
        if lhs is None:
            return [CallInstr(None, node.func.id, node.args)]
        else:
            return [CallInstr(ast.Name(lhs, ast.Store()), node.func.id, node.args)]

    def visit_Compare(self, node, lhs):
        left = node.left
        op = node.op
        right = node.right
        tag = ''
        if node.type == 'f32':
            tag = instrs.tag['float']
            return [SetInstr(Val(ast.Name(lhs, ast.Store())), Val(left), op, Val(right), node.type),
                    MoveInstr(Typ(ast.Name(lhs, ast.Store())), ast.Num(tag),'', 'u32')]
        elif node.type == 's32' or node.type == 'u32':
            tag = instrs.tag['int']
            #Since ints return 0xFFFFFFFF on True, it must be turned into the value 1 with an "and"
            return [SetInstr(Val(ast.Name(lhs, ast.Store())), Val(left), op, Val(right), node.type),
                    MoveInstr(Typ(ast.Name(lhs, ast.Store())), ast.Num(tag),'', 'u32'),
                    AndInstr(Val(ast.Name(lhs, ast.Store())), Val(ast.Name(lhs, ast.Store())), ast.Num(1))]
        else:
            raise Exception('Unkown type %s' % node.type)

    def visit_DeclareArray(self, node):
        return [node]

    def visit_Expr(self, node):
        return visit(self, node.value, None)

    def visit_FunctionDef(self, node):
        stmts = reduce(list.__add__, [visit(self, i) for i in node.body])
        return [ast.FunctionDef(node.name, node.args, stmts, node.decorator_list)]

    def visit_GetTag(self, node, lhs):
        return [Typ(node.arg)]

    def visit_GetType(self, node, lhs):
        if node.typ == 'big':
            movetype = 'u64'
        elif node.typ == 'int' or node.typ == 'bool':
            movetype = 's32'
        elif node.typ == 'float':
            movetype = 'f32'
        return [MoveInstr(Val(ast.Name(lhs, ast.Store())), Val(node.arg), '', movetype)]

    def visit_If(self, node):
        thens = reduce(list.__add__, [visit(self, i) for i in node.body])
        if node.orelse != []:
            orelses = reduce(list.__add__, [visit(self, i) for i in node.orelse])
        else:
            orelses = []
        #Generate labels for branch instructions
        orelse_label = generate_var("label")
        end_label = generate_var("label")
        pred = generate_var("pred")
        return [SetpInstr(ast.Name(pred, ast.Store()), Val(node.test), ast.Gt(), ast.Num(0)),\
                PredicateBranchInstr(ast.Name(pred, ast.Store()), ast.Name(orelse_label, ast.Load()), False)] + thens +\
               [PredicateBranchInstr(ast.Name(pred, ast.Store()), ast.Name(end_label, ast.Load()), True), Label(orelse_label)]+\
                orelses + [Label(end_label)]

    def visit_Lambda(self, node, lhs):
        stmts = reduce(list.__add__, [visit(self, i) for i in node.body])
        return [ast.FunctionDef(lhs, node.args, stmts, [])]

    def visit_LoadParam(self, node):
        return [node]

    def visit_Name(self, node, lhs):
        #If lhs and rhs are the same, no need to do anything
        if lhs == node.id:
            return []
        else:
            return [MoveInstr(ast.Name(lhs, ast.Store()), node, '.v2', 'b32')]

    def visit_Num(self, node, lhs):
        typ = type(node.n).__name__
        if typ  == 'int':
            return [MoveInstr(Val(ast.Name(lhs, ast.Store())), node, '', 's32')]
        elif typ == 'float':
            return [MoveInstr(Val(ast.Name(lhs, ast.Store())), node, '', 'f32')]
        else:
            raise Exception('Unknown type %s' % typ)
       
    def visit_Return(self, node):
        return [MoveInstr(Val(ast.Name('%rval', ast.Load())), Val(node.value), '', 'b32'),
                MoveInstr(Typ(ast.Name('%rval', ast.Load())), Typ(node.value), '', 's32'),
                ReturnInstr()]

    def visit_SetSubscript(self, node):
        return [StoreLocalInstr(node.container, node.val, node.key)]

    def visit_SetType(self, node, lhs):
        if node.typ == 'big':
            movetype = 'u32'
        elif node.typ == 'int' or node.typ == 'bool':
            movetype = 's32'
        elif node.typ == 'float':
            movetype = 'f32'
        return [MoveInstr(Typ(ast.Name(lhs, ast.Store())), ast.Num(instrs.tag[node.typ]), '', 'u32'),
                MoveInstr(Val(ast.Name(lhs, ast.Store())), Val(node.arg), '', movetype)]

    def visit_Subscript(self, node, lhs):
        if isinstance(node.slice, ast.Index):
            node.slice.value.n = node.slice.value.n + 1
        else:
            raise Exception('No slicing allowed in array index')
        return [LoadGlobalInstr(ast.Name(lhs, ast.Store()), node.value, node.slice)]


