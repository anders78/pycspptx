import ast
import instrs

class ExplicateVisitor(ast.NodeVisitor):
    def visit_Module(self, node):
        stmts = []
        for i in node.body:
            meth = getattr(self, 'visit_'+type(i).__name__)
            stmts = stmts + [meth(i)]
        return ast.Module(stmts)

    def visit_FunctionDef(self, node):
        body = []
        for i in node.body:
            stmt = getattr(self, 'visit_'+type(i).__name__)(i)
            body = body + [stmt]
        return ast.FunctionDef(node.name, node.args, body, node.decorator_list)

    def visit_Expr(self, node):
        value = getattr(self, 'visit_'+type(node.value).__name__)(node.value)
        return ast.Expr(value)

    def visit_Assign(self, node):
        rhs = getattr(self, 'visit_'+type(node.value).__name__)(node.value)
        lhs = node.targets[0]
        if isinstance(lhs, ast.Name):
            if lhs.id not in instrs.varlist:
                instrs.varlist[lhs.id] = 32
            return ast.Assign(node.targets, rhs)
        elif isinstance(lhs, ast.Subscript):
            container = getattr(self, type(lhs.value).__name__)(lhs.value)
            key = getattr(self, type(lhs.slice).__name__)(lhs.slice)
            return instrs.SetSubscript(container, key, rhs)
        else:
            raise Exception('Unrecognized lhs in Assign')

    #If(expr test, stmt* body, stmt* orelse)
    def visit_If(self, node):
        test = getattr(self, 'visit_'+type(node.test).__name__)(node.test)
        body_stmts = []
        for i in node.body:
            stmt = getattr(self, 'visit_'+type(i).__name__)(i)
            body_stmts = body_stmts + [stmt]
        orelse_stmts = []
        for i in node.orelse:
            stmt = getattr(self, 'visit_'+type(i).__name__)(i)
            orelse_stmts = orelse_stmts + [stmt]
        return ast.If(test, body_stmts, orelse_stmts)

    #For(expr target, expr iter, stmt* body, stmt* orelse)
    #NO ELSE PART SUPPORTET! ONLY WORKS FOR ITER & TARGET READABLE IN PYTHON
#    def visit_For(self, node):
##        target = getattr(self, 'visit_'+type(node.target).__name__)(node.target)
##        iter_expr = getattr(self, 'visit_'+type(node.iter).__name__)(node.iter)
#        body_stmts = []
#        for i in node.body:
#            stmt = getattr(self, 'visit_'+type(i).__name__)(i)
#            body_stmts = body_stmts + [stmt]
#        orelse_stmts = []
#        for i in node.orelse:
#            stmt = getattr(self, 'visit_'+type(i).__name__)(i)
#            orelse_stmts = orelse_stmts + [stmt]
#        return ast.For(node.target, node.iter, body_stmts, orelse_stmts)

    def visit_List(self, node):
        #Place length of list as first element
#        elts = [getattr(self, 'visit_'+type(i).__name__)(i) for i in [ast.Num(len(node.elts))]+node.elts]
#        return instrs.InjectFrom('big', ast.List([ast.Num(len(node.elts))]+node.elts, node.ctx))
        return ast.List([ast.Num(len(node.elts))]+node.elts, node.ctx)

    def visit_ListComp(self, node):
        #Warning! Hack to allow list comprehension to make list of floats
        l = [ast.Num(float(i)) for i in range(node.generators[0].iter.args[0].n)]
        #elts = [getattr(self, 'visit_'+type(i).__name__)(i) for i in [ast.Num(len(l))]+l]
        #return instrs.InjectFrom('big', ast.List(elts, ast.Load()))
        return ast.List([ast.Num(len(l))]+l, ast.Load())

#(expr value, slice slice, expr_context ctx)
    def visit_Subscript(self, node):
        value = getattr(self, 'visit_'+type(node.value).__name__)(node.value)
#        sli = getattr(self, 'visit_'+type(node.slice).__name__)(node.slice)
        return ast.Subscript(value, node.slice, node.ctx)

    def visit_Index(self, node):
        value = getattr(self, 'visit_'+type(node.value).__name__)(node.value)
        return ast.Index(value)

    def visit_Num(self, node):
        return instrs.InjectFrom(type(node.n).__name__, node)

    def visit_Name(self, node):
        if node.id == 'True':
            return instrs.InjectFrom('bool', ast.Num(True))
        elif node.id == 'False':
            return instrs.InjectFrom('bool', ast.Num(False))
        else:
            if node.id not in instrs.varlist:
                instrs.varlist[node.id] = 32
            return node

    def visit_Return(self, node):
        value = getattr(self, 'visit_'+type(node.value).__name__)(node.value)
        return ast.Return(value)

    # Taking advantage of the bit representations of bool's to avoid if's.
    # Also, not doing any error checking, for example, adding an integer to a list.
    def visit_BinOp(self, node):
        left = getattr(self, 'visit_'+type(node.left).__name__)(node.left)
        right = getattr(self, 'visit_'+type(node.right).__name__)(node.right)
        op = node.op
#        if isinstance(op, ast.Pow):
#            if node.right.n != 2:
#                raise Exception('Currently only squaring is allowed')
#            else:
#                op = ast.Mult()
#                right = left
        def result(l, r):
            return ast.IfExp(instrs.Compare(instrs.Typ(l), ast.Eq(),  ast.Num(instrs.tag['int']), 'u32'), #If
                             instrs.InjectFrom('int', instrs.BinOp(instrs.Val(l), op, instrs.Val( r), 's32')), #Then
                             instrs.InjectFrom('float', instrs.BinOp(instrs.Val(l), op, instrs.Val(r), 'f32'))) #Else
#            return ast.IfExp(instrs.Compare(instrs.Typ(l), ast.Eq(),  ast.Num(instrs.tag['int']), 'u32'), #If
#                             instrs.InjectFrom('int', instrs.BinOp(instrs.Val(l), op, instrs.Val( r), 's32')), #Then
#                             ast.IfExp(instrs.Compare(instrs.Typ(l), ast.Eq(), ast.Num(instrs.tag['bool']), 'u32'), #Else if
#                                       instrs.InjectFrom('int', instrs.BinOp(instrs.Val(l), op, instrs.Val(r), 'u32')),#Then
#                                       instrs.InjectFrom('float', instrs.BinOp(instrs.Val(l), op, instrs.Val(r), 'f32')))) #Else
        return instrs.letify(left, lambda l: instrs.letify(right, lambda r: result(l, r)))

    def visit_Compare(self, node):
        left = getattr(self, 'visit_'+type(node.left).__name__)(node.left)
        right = getattr(self, 'visit_'+type(node.comparators[0]).__name__)(node.comparators[0])
        op = node.ops[0]
        def result(l, r):
            return ast.IfExp(instrs.Compare(instrs.Typ(l), ast.Eq(),  ast.Num(instrs.tag['int']), 'u32'), #If
                             instrs.InjectFrom('int', instrs.Compare(instrs.Val(l), op, instrs.Val( r), 's32')), #Then
                             instrs.InjectFrom('float', instrs.Compare(instrs.Val(l), op, instrs.Val(r), 'f32'))) #Else
#            return ast.IfExp(instrs.Compare(instrs.Typ(l), ast.Eq(),  ast.Num(instrs.tag['int']), 'u32'), #If
#                             instrs.InjectFrom('int', instrs.Compare(instrs.Val(l), op, instrs.Val( r), 's32')), #Then
#                             ast.IfExp(instrs.Compare(instrs.Typ(l), ast.Eq(), ast.Num(instrs.tag['bool']), 'u32'), #Else if
#                                       instrs.InjectFrom('int', instrs.Compare(instrs.Val(l), op, instrs.Val(r), 'u32')),#Then
#                                       instrs.InjectFrom('float', instrs.Compare(instrs.Val(l), op, instrs.Val(r), 'f32')))) #Else
        return instrs.letify(left, lambda l: instrs.letify(right, lambda r: result(l, r)))

    def visit_UnaryOp(self, node):
        if isinstance(node.operand, ast.Num) and isinstance(node.operand.n, int):
            if isinstance(node.op, ast.USub):
                return instrs.InjectFrom('int', ast.Num(int(- node.operand.n)))
            else:
                raise Exception('Unary operation %s not supported' % type(node.op).__name__)
        else:
            #This branch not working at the moment.
            expr = getattr(self, 'visit_'+type(node.operand).__name__)(node.operand)
            return instrs.InjectFrom('int', ast.UnaryOp(instrs.ProjectTo('int', expr)))

    def visit_Lambda(self, node):
        body_meth = getattr(self, 'visit_'+type(node.body).__name__)
        return ast.Lambda(node.args, body_meth(node.body))

    #Call(expr func, expr* args, keyword* keywords,expr? starargs, expr? kwargs)
    def visit_Call(self, node):
#        func = getattr(self, 'visit_' + type(node.func).__name__)(node.func)
        if isinstance(node.func, ast.Name) and node.func.id in instrs.builtin_functions:
            if node.func.id == 'range':
                if isinstance(node.args[0], ast.Num):
                    args = [i.n for i in node.args]
                    elts = [ast.Num(i) for i in range(*args)]
                    return self.visit_List(ast.List(elts, ast.Load()))
                else:
                    args = [getattr(self, 'visit_' + type(i).__name__)(i) for i in node.args]
                    return ast.Call(node.func, args, node.keywords, node.starargs, node.kwargs)
            elif node.func.id == 'reduce':
                if not (len(node.args) == 2 and \
                        isinstance(node.args[0], ast.Lambda)):
                    raise Exception('Wrong input for builtin function reduce')
                else:
                    args = [getattr(self, 'visit_' + type(i).__name__)(i) for i in node.args]
                    return ast.Call(node.func, args, node.keywords, node.starargs, node.kwargs)
                #return ast.Call(node.func, args, node.keywords, node.starargs, node.kwargs)
        else:
            args = [getattr(self, 'visit_' + type(i).__name__)(i) for i in node.args]
            return ast.Call(node.func, args, node.keywords, node.starargs, node.kwargs)

    def visit_While(self, node):
        #Placeholder
        stmts = []
        for i in node.body:
            meth = getattr(self, 'visit_'+type(i).__name__)
            stmts = stmts + [meth(i)]
        return ast.While(node.test, stmts, node.orelse)
