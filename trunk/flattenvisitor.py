import ast
from instrs import *

####################################################
### FlattenVisitor                               ###
### Input: An explicated AST                     ###
### Output: An explicated AST containing         ###
### only flattened expressions. Ie. all          ###
### instruction operands are either constants or ###
### variables, not other instructions.           ###
###                                              ###
### Statements return a list of nodes            ###
### Expressions return (node, [nodes])           ###
####################################################

class FlattenVisitor(ast.NodeVisitor):
    def visit_Module(self, node):
        stmts = reduce(list.__add__, [visit(self, i) for i in node.body])
        return ast.Module(stmts)

    ##################
    ### Statements ###
    ##################
    def visit_Assign(self, node):
        (rhs,stmts) = visit(self, node.value, False)
        return stmts + [ast.Assign(node.targets, rhs)]

    def visit_DeclareGlobal(self, node):
        return [node]

    def visit_Expr(self, node):
        (expr, stmts) = visit(self, node.value, False)
        return stmts + [ast.Expr(expr)]

    def visit_FunctionDef(self, node):
        #Entryfunction - handle arguments
        if instrs.entryFunc is None:
            #Set entry function name
            instrs.entryFunc = node.name
            #Handle arguments
            for i in range(len(node.args.args)):
                #Int argument
                if instrs.args[i][0] == 'int':
                    node.body = [ast.Assign([node.args.args[i]], SetType('int', ast.Num(instrs.args[i][1])))] + node.body
                    instrs.varlist[node.args.args[i].id] = 32
                #Float argument
                elif instrs.args[i][0] == 'float':
                    node.body = [ast.Assign([node.args.args[i]], SetType('float', ast.Num(instrs.args[i][1])))] + node.body
                    instrs.varlist[node.args.args[i].id] = 32
                #Channel argument
                elif instrs.args[i][0] == 'ChannelEndRead' or instrs.args[i][0] == 'ChannelEndWrite':
                    pass

        stmts = reduce(list.__add__, [visit(self, i) for i in node.body])
        return [ast.FunctionDef(node.name, node.args, stmts, node.decorator_list)]

    def visit_If(self, node):
        (test, test_stmt) = visit(self, node.test, True)
        body_stmts = reduce(list.__add__, [visit(self, i) for i in node.body])
        if node.orelse != []:
            orelse_stmts = reduce(list.__add__, [visit(self, i) for i in node.orelse])
        else:
            orelse_stmts = []
        return test_stmt + [ast.If(test, body_stmts, orelse_stmts)]

    def visit_LoadParam(self, node):
        return [node]

    def visit_Return(self, node):
        (rhs,stmts) = visit(self, node.value, True)
        return stmts + [ast.Return(rhs)]

    def visit_SetSubscript(self, node):
        tmp = generate_var('tmp')
        (value, stmts1) = visit(self, node.value, True)
        return stmts1 + [SetSubscriptExpr(ast.Name(tmp, ast.Store()), node.container, value, node.key)]

    def visit_While(self, node):
        if isinstance(node.test, ast.Name) and node.test.id == 'True':
            #Special case of while True
            stmts = reduce(list.__add__,[visit(self, i) for i in node.body])
            return stmts
        else:
            (test, stmts1) = visit(self, node.test, True)
            body_stmts = reduce(list.__add__, [visit(self, i) for i in node.body])
            return stmts1 + [ast.While(test, body_stmts+stmts1, node.orelse)]

    ###################
    ### Expressions ###
    ###################
    def visit_BinOp(self, node, simple):
        (left, stmt1) = visit(self, node.left, True)
        (right, stmt2) = visit(self, node.right, True)
        if simple:
            tmp = generate_var('tmp')
            return (ast.Name(tmp,ast.Load()), 
                    stmt1 + stmt2 + 
                    [ast.Assign([ast.Name(tmp,ast.Store())], 
                                BinOp(left, node.op, right, node.type))])
        else:
            return (BinOp(left, node.op, right, node.type), stmt1 + stmt2)

    def visit_Call(self, node, simple):
        if isinstance(node.func, ast.Name):
            channel_vars[node.func.id] = len(node.args)
            args = stmts = []
            for i in node.args:
                (arg, stmt) = visit(self, i, True)
                args = args + [arg]
                stmts = stmts + stmt
            if simple:
                tmp = generate_var('tmp')
                return (ast.Name(tmp, ast.Load()), 
                        stmts + [ast.Assign([ast.Name(tmp, ast.Store())], \
                                 ast.Call(node.func, args, node.keywords,\
                                          node.starargs, node.kwargs))])
            else:
                return (ast.Call(node.func, args, node.keywords, node.starargs, node.kwargs), stmts)
        else:
            raise Exception ('Only calls to named functions allowed')

    def visit_Compare(self, node, simple):
        (left,stmt1) = visit(self, node.left, True)
        (right,stmt2) = visit(self, node.right, True)
        compare = Compare(left, node.op, right, node.type)
        if simple:
            tmp = generate_var('tmp')
            return (ast.Name(tmp, ast.Load()), 
                    stmt1 + stmt2 + [ast.Assign([ast.Name(tmp, ast.Store())], compare)])
        else:
            return (compare, stmt1 + stmt2)

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
        return (ast.Name(tmp, ast.Load()), 
                test_stmt + 
                [ast.If(test, body_stmt + [ast.Assign([ast.Name(tmp, ast.Store())], body)], 
                        orelse_stmt + [ast.Assign([ast.Name(tmp, ast.Store())], orelse)])])

    def visit_BoolOp(self, node, simple):
        (left, stmt1) = visit(self, node.values[0], True)
        (right, stmt2) = visit(self, node.values[1], True)
        #Transform to IfExp

        if isinstance(node.op, ast.And):
            op = ast.Gt()
        elif isinstance(node.op, ast.Or):
            op = ast.Eq()
        else:
            raise Exception('Unknown BoolOp operator')
        #op = and:
        n = ast.IfExp(Compare(node.values[0], op, ast.Num(0), 'u32'),
                      node.values[1], node.values[0])
        return self.visit_IfExp(n, simple)

#        if simple:
#            tmp = generate_var('tmp')
#            return (ast.Name(tmp, ast.Load()),
#                    stmt1 + stmt2 +
#                    [ast.Assign([ast.Name(tmp, ast.Store())],
#                    ast.BoolOp(node.op, [left, right]))])
#        else: 
#            return (ast.BoolOp(node.op, [left, right]), stmt1 + stmt2)

    def visit_Lambda(self, node, simple):
        (arg, stmts) = visit(self, node.body, True)
        if simple:
            #Used when lambda not assigned to anything. Currently, 
            #only ONE of these can exist in the program at once
            tmp = '%lambda'
            return (ast.Name(tmp, ast.Load()), [ast.Assign([ast.Name(tmp, ast.Store())], ast.Lambda(node.args, stmts + [ast.Return(arg)]))])
        else:
            return (ast.Lambda(node.args, stmts + [ast.Return(arg)]), [])

    def visit_Let(self, node, simple):
        (rhs_res, rhs_stmt) = visit(self, node.rhs, False)
        (body_res, body_stmt) = visit(self, node.body, True)
        return (body_res, rhs_stmt + [ast.Assign([ast.Name(node.var, ast.Load())], rhs_res)] + body_stmt)

    def visit_List(self, node, simple):
        tmp = generate_var('tmp') 
        return (ast.Name(tmp, ast.Load()),
                [DeclareArray(ast.Name(tmp, ast.Store()), node.elts)])

    def visit_Name(self, node, simple):
        return node, []

    def visit_Num(self, node, simple):
        return node, []

    def visit_SetType(self, node, simple):
        (arg, stmt) = visit(self, node.arg, True)
        tmp = generate_var('tmp')
        rhs = SetType(node.typ, arg)
        return (ast.Name(tmp, ast.Load()), stmt + [ast.Assign([ast.Name(tmp, ast.Store())], rhs)])

    def visit_Subscript(self, node, simple):
        (value_res, value_stmt) = visit(self, node.value, True)
        rhs = ast.Subscript(value_res, node.slice, node.ctx)
        if simple:
            tmp = generate_var('tmp')
            return (ast.Name(tmp, ast.Load()), value_stmt + [ast.Assign([ast.Name(tmp, ast.Store())], rhs)])
        else:
            return (rhs, value_stmt)

    def visit_Typ(self, node, simple):
        (expr, stmts) = visit(self, node.value, True)
        tmp = generate_var('tmp')
        return (Typ(expr), stmts)

    def visit_Val(self, node, simple):
        (expr, stmts) = visit(self, node.value, True)
        tmp = generate_var('tmp')
        return (Val(expr), stmts)


