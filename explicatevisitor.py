import ast
from instrs import *

class ExplicateVisitor(ast.NodeVisitor):
    def visit_Module(self, node):
        stmts = []
        for i in node.body:
            stmts = stmts + [visit(self, i)]
        return ast.Module(stmts)

    def visit_FunctionDef(self, node):
        body = []
        for i in node.body:
            body = body + [visit(self, i)]
            
        return ast.FunctionDef(node.name, node.args, body, node.decorator_list)

    def visit_Expr(self, node):
        return ast.Expr(visit(self,node.value))

    def visit_Assign(self, node):
        rhs = visit(self, node.value)
        lhs = node.targets[0]
        if isinstance(lhs, ast.Name):
            if lhs.id not in varlist:
                varlist[lhs.id] = 32
            return ast.Assign(node.targets, rhs)
        elif isinstance(lhs, ast.Subscript):
            container = visit(self, lhs.value)
            key = visit(self, lhs.slice)
            return SetSubscript(container, key, rhs)
        else:
            raise Exception('Unrecognized lhs in Assign')

    def visit_If(self, node):
        test = visit(self, node.test)
        body_stmts = []
        for i in node.body:
            stmt = visit(self, i)
            body_stmts = body_stmts + [stmt]
        orelse_stmts = []
        for i in node.orelse:
            stmt = visit(self, i)
            orelse_stmts = orelse_stmts + [stmt]
        return ast.If(test, body_stmts, orelse_stmts)

    def visit_List(self, node):
        return ast.List([ast.Num(len(node.elts))]+node.elts, node.ctx)

    def visit_ListComp(self, node):
        #Warning! Hack to allow list comprehension to make list of floats
        l = [ast.Num(float(i)) for i in range(node.generators[0].iter.args[0].n)]
        return ast.List([ast.Num(len(l))]+l, ast.Load())

    def visit_Subscript(self, node):
        value = visit(self, node.value)
        return ast.Subscript(value, node.slice, node.ctx)

    def visit_Index(self, node):
        value = visit(self, node.value)
        return ast.Index(value)

    def visit_Num(self, node):
        return SetType(type(node.n).__name__, node)

    def visit_Name(self, node):
        if node.id == 'True':
            return SetType('bool', ast.Num(True))
        elif node.id == 'False':
            return SetType('bool', ast.Num(False))
        else:
            if node.id not in varlist:
                varlist[node.id] = 32
            return node

    def visit_Return(self, node):
        value = visit(self, node.value)
        return ast.Return(value)

    # Taking advantage of the bit representations of bool's to avoid if's.
    # Also, not doing any error checking, for example, adding an integer to a list.
    def visit_BinOp(self, node):
        left = visit(self, node.left)
        right = visit(self, node.right)
        op = node.op
        def result(l, r):
            return ast.IfExp(Compare(Typ(l), ast.Eq(),  ast.Num(tag['int']), 'u32'), #If
                             SetType('int', BinOp(Val(l), op, Val( r), 's32')), #Then
                             SetType('float', BinOp(Val(l), op, Val(r), 'f32'))) #Else
        return letify(left, lambda l: letify(right, lambda r: result(l, r)))

    def visit_UnaryOp(self, node):
        if isinstance(node.operand, ast.Num) and isinstance(node.operand.n, int):
            if isinstance(node.op, ast.USub):
                return SetType('int', ast.Num(int(- node.operand.n)))
            else:
                raise Exception('Unary operation %s not supported' % type(node.op).__name__)
        else:
            #This branch not working at the moment.
            expr = visit(self, node.operand)
            return SetType('int', ast.UnaryOp(node.op, GetType('int', expr)))

    def visit_Compare(self, node):
        left = visit(self, node.left)
        right = visit(self, node.comparators[0])
        op = node.ops[0]
        def result(l, r):
            return ast.IfExp(Compare(Typ(l), ast.Eq(),  ast.Num(tag['int']), 'u32'), #If
                             SetType('int', Compare(Val(l), op, Val( r), 's32')), #Then
                             SetType('float', Compare(Val(l), op, Val(r), 'f32'))) #Else
        return letify(left, lambda l: letify(right, lambda r: result(l, r)))

    def visit_Lambda(self, node):
        return ast.Lambda(node.args, visit(self, node.body))

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in builtin_functions:
            #Set builtin to true
            builtin_functions[node.func.id] = True
            if node.func.id == 'range':
                if isinstance(node.args[0], ast.Num):
                    args = [i.n for i in node.args]
                    elts = [ast.Num(i) for i in range(*args)]
                    return ast.List([ast.Num(len(elts))]+elts, ast.Load())
            elif node.func.id == 'reduce':
                if not (len(node.args) == 2 and \
                        isinstance(node.args[0], ast.Lambda)):
                    raise Exception('Wrong input for builtin function reduce')
                else:
                    args = [visit(self, i) for i in node.args]
                    return ast.Call(node.func, args, node.keywords, node.starargs, node.kwargs)
            elif node.func.id == 'random':
                if not len(node.args) == 0:
                    raise Exception('No input allowed for builtin function random')
                else:
                    args = [visit(self, i) for i in node.args]
                    return ast.Call(node.func, args, node.keywords, node.starargs, node.kwargs)
        else:
            args = [visit(self, i) for i in node.args]
            return ast.Call(node.func, args, node.keywords, node.starargs, node.kwargs)

    def visit_While(self, node):
        #Placeholder
        stmts = []
        for i in node.body:
            stmts = stmts + [visit(self, i)]
        return ast.While(node.test, stmts, node.orelse)
