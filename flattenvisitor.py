import ast
import instrs

#Idea is to flatten the ast, so output is a new ast

class FlattenVisitor(ast.NodeVisitor):
    def visit_Module(self, node):
        stmts = []
        for i in node.body:
            meth = getattr(self, 'visit_'+type(i).__name__)
            stmts = stmts + meth(i)
        return ast.Module(stmts)

    #### Statements ####
    def visit_Assign(self, node):
        meth = getattr(self, 'visit_'+type(node.value).__name__)
        (rhs,stmts) = meth(node.value, False)
        return stmts + [ast.Assign(node.targets, rhs)]

    def visit_Expr(self, node):
        expr_meth = getattr(self, 'visit_'+type(node.value).__name__)
        (expr, stmts) = expr_meth(node.value, False)
        return stmts + [ast.Expr(expr)]

    def visit_FunctionDef(self, node):
        stmts = []
        #Entryfunction
        if instrs.entryFunc is None:
            instrs.entryFunc = node.name
            for i in range(len(node.args.args)):
                if instrs.args[i][0] == 'int':
                    node.body = [ast.Assign([node.args.args[i]], instrs.InjectFrom('int', ast.Num(instrs.args[i][1])))] + node.body
                    instrs.varlist[node.args.args[i].id] = 32
                elif instrs.args[i][0] == 'float':
                    node.body = [ast.Assign([node.args.args[i]], instrs.InjectFrom('float', ast.Num(instrs.args[i][1])))] + node.body
                    instrs.varlist[node.args.args[i].id] = 32
                elif instrs.args[i][0] == 'ChannelEndRead' or instrs.args[i][0] == 'ChannelEndWrite':
                    pass
                #Create a register named node.args.args[i].id (cin)
                #Load into register from globalmem
#                node.body = [instrs.DeclareGlobal('__cuda__'+node.name+ '_' +node.args.args[i].id + '_global')] + node.body
#                            ,instrs.LoadParam(node.args.args[i], ast.Name('__cuda__'+node.name+ '_' +node.args.args[i].id, ast.Load()))] + node.body
#                instrs.varlist[node.args.args[i].id] = 64
#            elif instrs.args[i][0] == 'ChannelEndWrite':
 #               pass
          
        for i in node.body:
            meth = getattr(self, 'visit_'+type(i).__name__)
            stmts = stmts + meth(i)
        return [ast.FunctionDef(node.name, node.args, stmts, node.decorator_list)]

    def visit_Return(self, node):
        meth = getattr(self, 'visit_'+type(node.value).__name__)
        (rhs,stmts) = meth(node.value, True)
        return stmts + [ast.Return(rhs)]

    def visit_While(self, node):
        if isinstance(node.test, ast.Name) and node.test.id == 'True':
            stmts = []
            for i in node.body:
                meth = getattr(self, 'visit_'+type(i).__name__)
                stmts = stmts + meth(i)
            return stmts
        else:
            raise Exception('Currently only while(True) loops supported')

    def visit_If(self, node):
        (test, test_stmt) = getattr(self, 'visit_'+type(node.test).__name__)(node.test, True)
        body_stmts = []
        for i in node.body:
            stmt = getattr(self, 'visit_'+type(i).__name__)(i)
            body_stmts = body_stmts + stmt
        orelse_stmts = []
        for i in node.orelse:
            stmt = getattr(self, 'visit_'+type(i).__name__)(i)
            orelse_stmts = orelse_stmts + stmt
        return test_stmt + [ast.If(test, body_stmts, orelse_stmts)]

#    def visit_For(self, node):
##        (target, target_stmt) = getattr(self, 'visit_'+type(node.target).__name__)(node.target, True)
##        (iter_expr, iter_stmt) = getattr(self, 'visit_'+type(node.iter).__name__)(node.iter, True)
#        body_stmts = []
#        for i in node.body:
#            stmt = getattr(self, 'visit_'+type(i).__name__)(i)
#            body_stmts = body_stmts + stmt
#        orelse_stmts = []
#        for i in node.orelse:
#            stmt = getattr(self, 'visit_'+type(i).__name__)(i)
#            orelse_stmts = orelse_stmts + stmt
#        return [ast.For(node.target, node.iter, body_stmts, orelse_stmts)]

    def visit_DeclareGlobal(self, node):
        return [node]

    def visit_LoadParam(self, node):
        return [node]

    #### Expressions ####
    def visit_Lambda(self, node, simple):
        (arg, stmts) = getattr(self, 'visit_'+type(node.body).__name__)(node.body, True)
        if simple:
            tmp = 'lambda'
            #Make sure flatten doesnt move stmts out of the function
            return (ast.Name(tmp, ast.Load()), [ast.Assign([ast.Name(tmp, ast.Store())], ast.Lambda(node.args, stmts + [ast.Return(arg)]))])
        else:
            return (ast.Lambda(node.args, stmts + [ast.Return(arg)]), [])

    def visit_Call(self, node, simple):
        if isinstance(node.func, ast.Name):
            args = []
            stmts = []
            for i in node.args:
                (arg, stmt) = getattr(self, 'visit_'+type(i).__name__)(i, True)
                args = args + [arg]
                stmts = stmts + stmt
            if simple:
                tmp = instrs.generate_var('tmp')
                return (ast.Name(tmp, ast.Load()), stmts + [ast.Assign([ast.Name(tmp, ast.Store())], \
                                                                   ast.Call(node.func, args, node.keywords,\
                                                                            node.starargs, node.kwargs))])
            else:
                return (ast.Call(node.func, args, node.keywords, node.starargs, node.kwargs), stmts)
        else:
            raise Exception ('Only calls to named functions allowed')
#        #If its a call to range, replace with the actual array
#        if node.func.id == 'range':
#            elts = []
#            for i in range(node.args[0].n):
#                elts.extend([ast.Num(i)])
#            return (ast.List(elts, ast.Load()), [])

    def visit_BinOp(self, node, simple):
        (left, stmt1) = getattr(self, 'visit_'+type(node.left).__name__)(node.left, True)
        (right, stmt2) = getattr(self, 'visit_'+type(node.right).__name__)(node.right, True)
        if simple:
            tmp = instrs.generate_var('tmp')
            return (ast.Name(tmp,ast.Load()), stmt1+stmt2 + [ast.Assign([ast.Name(tmp,ast.Store())], instrs.BinOp(left, node.op, right, node.type))])
        else:
            return (instrs.BinOp(left, node.op, right, node.type), stmt1 + stmt2)

    def visit_UnaryOp(self, node, simple):
        (expr,stmts) = getattr(self, 'visit_'+type(node.operand).__name__)(node.operand, True)
        if simple:
            tmp = instrs.generate_var('tmp')
            return (ast.Name(tmp, ast.Load()), stmts + [ast.Assign([ast.Name(tmp, ast.Store())], ast.UnaryOp(node.op, expr))])
        else:
            return (ast.UnaryOp(node.op, expr), stmts)

    def visit_Let(self, node, simple):
        (rhs_res, rhs_stmt) = getattr(self, 'visit_'+type(node.rhs).__name__)(node.rhs, False)
        (body_res, body_stmt) = getattr(self, 'visit_'+type(node.body).__name__)(node.body, True)
        return (body_res, rhs_stmt + [ast.Assign([ast.Name(node.var, ast.Load())], rhs_res)] + body_stmt)

    def visit_InjectFrom(self, node, simple):
        (arg, stmt) = getattr(self, 'visit_'+type(node.arg).__name__)(node.arg, True)
        tmp = instrs.generate_var('tmp')
        rhs = instrs.InjectFrom(node.typ, arg)
        return (ast.Name(tmp, ast.Load()), stmt + [ast.Assign([ast.Name(tmp, ast.Store())], rhs)])

    def visit_ProjectTo(self, node, simple):
        (arg, stmt) = getattr(self, 'visit_'+type(node.arg).__name__)(node.arg, True)
        tmp = instrs.generate_var('tmp')
        rhs = instrs.ProjectTo(node.typ, arg)
        return (ast.Name(tmp, ast.Load()), stmt + [ast.Assign([ast.Name(tmp, ast.Store())], rhs)])

    def visit_IfExp(self, node, simple):
        (test, test_stmt) = getattr(self, 'visit_'+type(node.test).__name__)(node.test, True)
        (body, body_stmt) = getattr(self, 'visit_'+type(node.body).__name__)(node.body, True)
        (orelse, orelse_stmt) = getattr(self, 'visit_'+type(node.orelse).__name__)(node.orelse, True)     
        tmp = instrs.generate_var('tmp')
        return (ast.Name(tmp, ast.Load()), test_stmt + [ast.If(test, body_stmt + [ast.Assign([ast.Name(tmp, ast.Store())], body)] , orelse_stmt + [ast.Assign([ast.Name(tmp, ast.Store())], orelse)])])

    def visit_Compare(self, node, simple):
        (left,stmt1) = getattr(self, 'visit_'+type(node.left).__name__)(node.left, True)
        (right,stmt2) = getattr(self, 'visit_'+type(node.right).__name__)(node.right, True)
        compare = instrs.Compare(left, node.op, right, node.type)
        if simple:
            tmp = instrs.generate_var('tmp')
            return (ast.Name(tmp, ast.Load()), stmt1 + stmt2 + [ast.Assign([ast.Name(tmp, ast.Store())], compare)])
        else:
            return (compare, stmt1 + stmt2)

#    def visit_GetTag(self, node, simple):
#        print "Flatten: GetTag"
#        (expr, stmts) = getattr(self, 'visit_'+type(node.arg).__name__)(node.arg, True)
#        tmp = instrs.generate_var('tmp')
#        rhs = instrs.GetTag(expr)
#        return (ast.Name(tmp, ast.Load()), stmts + [ast.Assign([ast.Name(tmp, ast.Store())], rhs)])

    def visit_Typ(self, node, simple):
        (expr, stmts) = getattr(self, 'visit_'+type(node.value).__name__)(node.value, True)
        tmp = instrs.generate_var('tmp')
        return (instrs.Typ(expr), stmts)
#        return (ast.Name(tmp, ast.Load()), stmts + [ast.Assign([ast.Name(tmp, ast.Store())], rhs)])

    def visit_Val(self, node, simple):
        (expr, stmts) = getattr(self, 'visit_'+type(node.value).__name__)(node.value, True)
        tmp = instrs.generate_var('tmp')
        return (instrs.Val(expr), stmts)

    #Subscript(expr value, slice slice, expr_context ctx)
    def visit_Subscript(self, node, simple):
        (value_res, value_stmt) = getattr(self, 'visit_'+type(node.value).__name__)(node.value, True)
#        (slice_res, slice_stmt) = getattr(self, 'visit_'+type(node.slice).__name__)(node.slice, True)
        rhs = ast.Subscript(value_res, node.slice, node.ctx)
        if simple:
            tmp = instrs.generate_var('tmp')
            return (ast.Name(tmp, ast.Load()), value_stmt + [ast.Assign([ast.Name(tmp, ast.Store())], rhs)])
        else:
            return (rhs, value_stmt)
        
#    def visit_Index(self, node, simple):
#        (value_res, value_stmt) = getattr(self, 'visit_'+type(node.value).__name__)(node.value, True)
#        return (ast.Index(value_res), value_stmt)

#    def visit_Index(self, node, simple):
#        if isinstance(node.value, ast.Name):
#            address = node.value.id
#        elif isinstance(node.value, ast.Num):
#            address = node.value.n
#        else:
#            raise Exception('Unknown index type, only vars and values allowed')
#        idx_op = ast.BinOp(instrs.Address(address), ast.Mult(), instrs.ImmAddress(4))
#        (expr, stmt) = getattr(self, 'visit_BinOp')(idx_op, True)
#        return expr, stmt

    def visit_Num(self, node, simple):
        return node, []

    def visit_Name(self, node, simple):
        return node, []

#    def visit_List(self, node, simple):
#        stmts = []
#        tmp = instrs.generate_var('tmp') #Formerly list
#        pos = 0
#        for i in node.elts:
#            (elem_res, elem_stmt) = getattr(self, 'visit_'+type(i).__name__)(i, True)
#            stmts = stmts + elem_stmt + [instrs.SetSubscript(ast.Name(tmp, ast.Store()), elem_res, ast.Index(ast.Num(pos)))]
#            pos = pos + 1
#        return (ast.Name(tmp, ast.Load()), [instrs.DeclareArray(ast.Name(tmp, ast.Store()), len(node.elts))] + stmts)

    def visit_List(self, node, simple):
        stmts = []
        tmp = instrs.generate_var('tmp') #Formerly list
        return (ast.Name(tmp, ast.Load()), [instrs.DeclareArray(ast.Name(tmp, ast.Store()), node.elts)] + stmts)


