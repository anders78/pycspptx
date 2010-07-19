import ast
from instrs import *

#Idea is to flatten the ast, so output is a new ast

class FlattenVisitor(ast.NodeVisitor):
    def visit_Module(self, node):
        stmts = []
        for i in node.body:
            stmts = stmts + visit(self, i)
        return ast.Module(stmts)

    #### Statements ####
    def visit_Assign(self, node):
        (rhs,stmts) = visit(self, node.value, False)
        return stmts + [ast.Assign(node.targets, rhs)]

    def visit_Expr(self, node):
        (expr, stmts) = visit(self, node.value, False)
        return stmts + [ast.Expr(expr)]

    def visit_FunctionDef(self, node):
        stmts = []
        #Entryfunction
        if instrs.entryFunc is None:
            instrs.entryFunc = node.name
            for i in range(len(node.args.args)):
                if instrs.args[i][0] == 'int':
                    node.body = [ast.Assign([node.args.args[i]], SetType('int', ast.Num(instrs.args[i][1])))] + node.body
                    instrs.varlist[node.args.args[i].id] = 32
                elif instrs.args[i][0] == 'float':
                    node.body = [ast.Assign([node.args.args[i]], SetType('float', ast.Num(instrs.args[i][1])))] + node.body
                    instrs.varlist[node.args.args[i].id] = 32
                elif instrs.args[i][0] == 'ChannelEndRead' or instrs.args[i][0] == 'ChannelEndWrite':
                    pass
        for i in node.body:
            stmts = stmts + visit(self, i)
        return [ast.FunctionDef(node.name, node.args, stmts, node.decorator_list)]

    def visit_Return(self, node):
        (rhs,stmts) = visit(self, node.value, True)
        return stmts + [ast.Return(rhs)]

    def visit_While(self, node):
        if isinstance(node.test, ast.Name) and node.test.id == 'True':
            stmts = []
            for i in node.body:
                stmts = stmts + visit(self, i)
            return stmts
        else:
            raise Exception('Currently only while(True) loops supported')

    def visit_If(self, node):
        (test, test_stmt) = visit(self, node.test, True)
        body_stmts = []
        for i in node.body:
            stmt = visit(self, i)
            body_stmts = body_stmts + stmt
        orelse_stmts = []
        for i in node.orelse:
            stmt = visit(self, i)
            orelse_stmts = orelse_stmts + stmt
        return test_stmt + [ast.If(test, body_stmts, orelse_stmts)]

    def visit_DeclareGlobal(self, node):
        return [node]

    def visit_LoadParam(self, node):
        return [node]

    #### Expressions ####
    def visit_Lambda(self, node, simple):
        (arg, stmts) = visit(self, node.body, True)
        if simple:
            tmp = '%lambda'
            #Make sure flatten doesnt move stmts out of the function
            return (ast.Name(tmp, ast.Load()), [ast.Assign([ast.Name(tmp, ast.Store())], ast.Lambda(node.args, stmts + [ast.Return(arg)]))])
        else:
            return (ast.Lambda(node.args, stmts + [ast.Return(arg)]), [])

    def visit_Call(self, node, simple):
        if isinstance(node.func, ast.Name):
            args = []
            stmts = []
            for i in node.args:
                (arg, stmt) = visit(self, i, True)
                args = args + [arg]
                stmts = stmts + stmt
            if simple:
                tmp = generate_var('tmp')
                return (ast.Name(tmp, ast.Load()), stmts + [ast.Assign([ast.Name(tmp, ast.Store())], \
                                                                   ast.Call(node.func, args, node.keywords,\
                                                                            node.starargs, node.kwargs))])
            else:
                return (ast.Call(node.func, args, node.keywords, node.starargs, node.kwargs), stmts)
        else:
            raise Exception ('Only calls to named functions allowed')

    def visit_BinOp(self, node, simple):
        (left, stmt1) = visit(self, node.left, True)
        (right, stmt2) = visit(self, node.right, True)
        if simple:
            tmp = generate_var('tmp')
            return (ast.Name(tmp,ast.Load()), stmt1+stmt2 + [ast.Assign([ast.Name(tmp,ast.Store())], BinOp(left, node.op, right, node.type))])
        else:
            return (BinOp(left, node.op, right, node.type), stmt1 + stmt2)

#    def visit_UnaryOp(self, node, simple):
#        (expr,stmts) = visit(self, node.operand, True)
#        if simple:
#            tmp = generate_var('tmp')
#            return (ast.Name(tmp, ast.Load()), stmts + [ast.Assign([ast.Name(tmp, ast.Store())], ast.UnaryOp(node.op, expr))])
#        else:
#            return (ast.UnaryOp(node.op, expr), stmts)

    def visit_Let(self, node, simple):
        (rhs_res, rhs_stmt) = visit(self, node.rhs, False)
        (body_res, body_stmt) = visit(self, node.body, True)
        return (body_res, rhs_stmt + [ast.Assign([ast.Name(node.var, ast.Load())], rhs_res)] + body_stmt)

    def visit_SetType(self, node, simple):
        (arg, stmt) = visit(self, node.arg, True)
        tmp = generate_var('tmp')
        rhs = SetType(node.typ, arg)
        return (ast.Name(tmp, ast.Load()), stmt + [ast.Assign([ast.Name(tmp, ast.Store())], rhs)])

    def visit_GetType(self, node, simple):
        (arg, stmt) = visit(self, node.arg, True)
        tmp = generate_var('tmp')
        rhs = GetType(node.typ, arg)
        return (ast.Name(tmp, ast.Load()), stmt + [ast.Assign([ast.Name(tmp, ast.Store())], rhs)])

    def visit_IfExp(self, node, simple):
        (test, test_stmt) = visit(self, node.test, True)
        (body, body_stmt) = visit(self, node.body, True)
        (orelse, orelse_stmt) = visit(self, node.orelse, True)
        tmp = generate_var('tmp')
        return (ast.Name(tmp, ast.Load()), test_stmt + [ast.If(test, body_stmt + [ast.Assign([ast.Name(tmp, ast.Store())], body)] , orelse_stmt + [ast.Assign([ast.Name(tmp, ast.Store())], orelse)])])

    def visit_Compare(self, node, simple):
        (left,stmt1) = visit(self, node.left, True)
        (right,stmt2) = visit(self, node.right, True)
        compare = Compare(left, node.op, right, node.type)
        if simple:
            tmp = generate_var('tmp')
            return (ast.Name(tmp, ast.Load()), stmt1 + stmt2 + [ast.Assign([ast.Name(tmp, ast.Store())], compare)])
        else:
            return (compare, stmt1 + stmt2)

    def visit_Typ(self, node, simple):
        (expr, stmts) = visit(self, node.value, True)
        tmp = generate_var('tmp')
        return (Typ(expr), stmts)

    def visit_Val(self, node, simple):
        (expr, stmts) = visit(self, node.value, True)
        tmp = generate_var('tmp')
        return (Val(expr), stmts)

    def visit_Subscript(self, node, simple):
        (value_res, value_stmt) = visit(self, node.value, True)
        rhs = ast.Subscript(value_res, node.slice, node.ctx)
        if simple:
            tmp = generate_var('tmp')
            return (ast.Name(tmp, ast.Load()), value_stmt + [ast.Assign([ast.Name(tmp, ast.Store())], rhs)])
        else:
            return (rhs, value_stmt)
        
    def visit_Num(self, node, simple):
        return node, []

    def visit_Name(self, node, simple):
        return node, []

    def visit_List(self, node, simple):
#        stmts = []
        tmp = generate_var('tmp') 
        return (ast.Name(tmp, ast.Load()), [DeclareArray(ast.Name(tmp, ast.Store()), node.elts)])


