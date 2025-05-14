from typing import Optional

from antlr4.tree.TokenTagToken import TokenTagToken
from CodeStyle.JavaParser import JavaParser
from CodeStyle.JavaParserVisitor import JavaParserVisitor
from antlr4.TokenStreamRewriter import TokenStreamRewriter
from functools import wraps
from CodeStyle.ConfigClass import ConfigClass

class FormattingVisitor(JavaParserVisitor):
    def __init__(self, tokens, config: ConfigClass):
        self.rewriter : TokenStreamRewriter = TokenStreamRewriter(tokens)
        self.config:ConfigClass = config
        self.indent_level: int = 0
        self.imports = {
            'items': [],
            'start_index': -1,
            'end_index': -1
        }

    def visitImportDeclaration(self, ctx: JavaParser.ImportDeclarationContext):
        token_stream = self.rewriter.getTokenStream()
        if not self.config.imports["merge"]:
            if token_stream.get(ctx.stop.tokenIndex+1).type in [JavaParser.WS]:
                self.rewriter.replaceIndex(ctx.stop.tokenIndex+1, "\n")
            else:
                self.rewriter.insertBeforeIndex(ctx.stop.tokenIndex+1, "\n")

        if self.config.imports['order'] == "sort":
            if self.imports['start_index'] == -1:
                self.imports['start_index'] = ctx.start.tokenIndex
            self.imports['end_index'] = ctx.stop.tokenIndex
            self.imports['items'].append(self._get_import_text(ctx.start.tokenIndex, ctx.stop.tokenIndex))

        return self.visitChildren(ctx)
    
    def _get_import_text(self, start, stop):
        text = []
        for i in range(start, stop+1):
            text.append(self.rewriter.getTokenStream().get(i).text)
        return text[0] + " " + "".join(text[1:]).strip()
    
    def _order_imports(self):
        if self.imports['items']:
            self.rewriter.replaceRange(self.imports['start_index'], self.imports['end_index'], "\n".join(sorted(self.imports['items'])))
        
        # Used to help with the lack of a newline in the last import
        if not self.config.imports['merge']:
            self.rewriter.insertBeforeIndex(self.imports['end_index']+1, "\n")

    def visitClassDeclaration(self, ctx: JavaParser.ClassDeclarationContext):
        """
        Formats a Java class declaration according to configured style rules.
        
        Adjusts modifier order, whitespace, indentation, and brace placement for class declarations based on formatting configuration. Applies indentation and newline after the opening brace, and ensures proper formatting around the class body.
        """
        class_name = ctx.identifier().getText()
        modifiers = []
        parent = ctx.parentCtx

        # add new line before class declaration
        if self.config.imports['merge']:
            self.rewriter.insertBeforeToken(parent.start, "\n\n")
        else:
            self.rewriter.insertBeforeToken(parent.start, "\n")

        if isinstance(parent, JavaParser.TypeDeclarationContext):
            if parent.classOrInterfaceModifier():
                modifiers = [mod.getText() for mod in parent.classOrInterfaceModifier()]
                modifiers = self._sort_modifiers(modifiers, self.config.class_modifier_order)
        
        class_signature = f"{' '.join(modifiers)} class {class_name}".strip()
        self.rewriter.replaceRangeTokens(parent.start, ctx.identifier().stop, class_signature)

        class_body : JavaParser.ClassBodyContext = ctx.classBody()

        if class_body:
            open_brace = class_body.LBRACE().symbol
            close_brace = class_body.RBRACE().symbol
            
            self._remove_whitespace(open_brace.tokenIndex + 1)
            self._remove_whitespace(open_brace.tokenIndex - 1)
            
            self._remove_whitespace(close_brace.tokenIndex - 1)
            self._remove_whitespace(close_brace.tokenIndex + 1)

            self.rewriter.insertBeforeIndex(class_body.start.tokenIndex+1, f"{self._get_indent(additional_ident=1)}")

            if self.config.brace_style == "attach":
                self.rewriter.replaceSingleToken(open_brace, " {\n")
            else:
                self.rewriter.replaceSingleToken(open_brace, f"\n{self._get_indent()}"+"{\n")

            if class_body.getChildCount() > 2:
                brace_break = "\n"
            else:
                brace_break = ""

            self.rewriter.replaceSingleToken(close_brace, f"{brace_break}{self._get_indent()}" + "}")

            self.indent_level += 1

        
        return self.visitChildren(ctx)
    
    def visitMethodDeclaration(self, ctx: JavaParser.MethodDeclarationContext):
        return_type = ctx.typeTypeOrVoid().getText()
        method_name = ctx.identifier().getText()
        modifiers = []
        parent = ctx.parentCtx  
        grandparent: Optional[JavaParser.StatementContext] = None
        if isinstance(parent, JavaParser.MemberDeclarationContext):  
            grandparent = parent.parentCtx  
            if isinstance(grandparent, JavaParser.ClassBodyDeclarationContext):
                if grandparent.modifier():
                    modifiers = [mod.getText() for mod in grandparent.modifier()]
                    modifiers = self._sort_modifiers(modifiers, self.config.method_modifier_order)

        method_signature = f"{' '.join(modifiers)} {return_type} {method_name}".strip()

        if grandparent: 
            self.rewriter.replaceRangeTokens(grandparent.start, ctx.identifier().stop, f"\n{self._get_indent()}{method_signature}")

        return self.visitChildren(ctx)
    
    def visitStatement(self, ctx: JavaParser.StatementContext):
        if ctx.SWITCH():
            close_paren = ctx.RBRACE().getSymbol()
            open_brace = ctx.LBRACE().getSymbol()
            if self.config.brace_style == "attach":
                self.rewriter.replaceSingleToken(open_brace, " {")
            else:
                self.rewriter.replaceSingleToken(open_brace, f"\n{self._get_indent()}" + "{")
            self.rewriter.insertBeforeToken(close_paren, f"\n{self._get_indent()}")
        return self.visitChildren(ctx)


    @staticmethod
    def handle_indentation(method):
        """Decorator to automatically increase and decrease indentation."""
        @wraps(method)
        def wrapper(self, ctx):
            ignore_switch_case = method.__name__ == "visitSwitchBlockStatementGroup" and self.config.indents['switch_case_labels'] != "indent"

            if not ignore_switch_case:
                self.indent_level += 1
            try:
                return method(self, ctx)
            finally:
                if not ignore_switch_case:
                    self.indent_level -= 1 
        return wrapper


    @handle_indentation
    def visitBlockStatement(self, ctx: JavaParser.BlockStatementContext):
        statement_start = ctx.start
        self.rewriter.insertBeforeToken(statement_start, f"\n{self._get_indent()}")
        return self.visitChildren(ctx)

    def visitSwitchLabel(self, ctx: JavaParser.SwitchLabelContext):
        lable_start = ctx.start
        self.rewriter.insertBeforeToken(lable_start, f"\n{self._get_indent()}")
        return super().visitSwitchLabel(ctx)

    @handle_indentation
    def visitSwitchBlockStatementGroup(self, ctx: JavaParser.SwitchBlockStatementGroupContext):
        return self.visitChildren(ctx)

    def visitBlock(self, ctx: JavaParser.BlockContext):
        open_brace = ctx.LBRACE().getSymbol()
        close_brace = ctx.RBRACE().getSymbol()
        parent = ctx.parentCtx 
        in_switch = False
        while parent:
            if isinstance(parent, JavaParser.SwitchBlockStatementGroupContext):
                in_switch = True
                break
            if isinstance(parent, JavaParser.FinallyBlockContext):
                in_switch = True
                break
            parent = parent.parentCtx  # Move up the tree


        if self.config.brace_style == "attach":
            self._remove_whitespace(open_brace.tokenIndex - 1) 
            if in_switch:
                self.rewriter.replaceSingleToken(open_brace, "{")
            else:
                self.rewriter.replaceSingleToken(open_brace, " {")
        else:
            self._remove_whitespace(open_brace.tokenIndex - 1) 
            if in_switch:
                self.rewriter.replaceSingleToken(open_brace, "{")
            self.rewriter.replaceSingleToken(open_brace, f"\n{self._get_indent()}" + "{")
        
        self.rewriter.replaceSingleToken(close_brace, f"\n{self._get_indent()}" + "}")
        return self.visitChildren(ctx)

    def _apply_bracket_alignment(self, open_paren, parameters, close_paren, parameter_size):
        match self.config.aligns['after_open_bracket']:
            case 'align':
                max_parameter_size = self.config.aligns['parameters_before_align']
                if not parameter_size > max_parameter_size:
                    return
                
                for i in range(max_parameter_size, parameter_size, max_parameter_size):
                    capture_pos = i * 2
                    parameter = parameters.getChild(capture_pos)
                    align_spaces = self._get_align_spaces(open_paren)
                    self.rewriter.insertBeforeToken(parameter.start, f"\n{align_spaces}")

            case 'dont_align':
                max_parameter_size = self.config.aligns['parameters_before_align']
                if not parameter_size > max_parameter_size:
                    return

                for i in range(max_parameter_size, parameter_size, max_parameter_size):
                    capture_pos = i * 2
                    parameter = parameters.getChild(capture_pos)
                    self.indent_level += 1
                    self.rewriter.insertBeforeToken(parameter.start, f"\n{self._get_indent()}")
                    self.indent_level -= 1

            case 'always_break':
                self.indent_level += 1
                self.rewriter.insertBeforeToken(parameters.start, f"\n{self._get_indent()}")
                self.indent_level -= 1

            case 'block_indent':
                self.indent_level += 1
                self.rewriter.insertBeforeToken(parameters.start, f"\n{self._get_indent()}")
                self.indent_level -= 1
                self.rewriter.insertBeforeIndex(close_paren.tokenIndex, f"\n{self._get_indent()}")
            
            case 'all_parameters_on_new_line':
                for i in range(1, parameter_size):
                    capture_pos = i * 2
                    parameter = parameters.getChild(capture_pos)
                    align_spaces = self._get_align_spaces(open_paren)
                    self.rewriter.insertBeforeToken(parameter.start, f"\n{align_spaces}")

    def _get_align_spaces(self, open_paren):
        token_stream = self.rewriter.getTokenStream()
        token_index = open_paren.tokenIndex
        spacer_length = 0
        while token_stream.get(token_index).type != JavaParser.WS:
            spacer_length += len(token_stream.get(token_index).text)
            token_index -= 1

        return " " * (spacer_length + (self.indent_level * self.config.indents['size']))         

    def _remove_whitespace(self, pos):
        while self.rewriter.getTokenStream().get(pos).type in [JavaParser.WS] or self.rewriter.getTokenStream().get(pos).text == "\n":
            self.rewriter.deleteToken(pos)
            pos -=1

    def _sort_modifiers(self, modifiers, order):
        """
        Sorts a list of modifiers according to a specified order.
        
        Modifiers not present in the order list are placed at the end in their original order.
        
        Args:
            modifiers: List of modifier strings to sort.
            order: List defining the desired order of modifiers.
        
        Returns:
            A new list of modifiers sorted according to the specified order.
        """
        return sorted(modifiers, key=lambda x: order.index(x) if x in order else len(order))
    
    def _get_indent(self, additional_ident =0):
        """
        Returns the current indentation string based on the configured style and level.
        
        Args:
            additional_ident: Optional number of additional indentation levels to apply.
        
        Returns:
            A string of spaces or tabs representing the current indentation.
        """
        match self.config.indents['type']:
            case "spaces":
                return " " * ((self.indent_level +additional_ident) * self.config.indents['size'])
            # may it appear as 8 spaces but it is actually configurable
            # in text editors so it should be as a size of indent_size
            case "tabs":
                return "\t" * (self.indent_level + additional_ident)
    
    
    def visitVariableDeclarator(self, ctx: JavaParser.VariableDeclaratorContext):
        """
        Formats variable declarator statements with appropriate spacing and indentation.
        
        Ensures spaces around the assignment operator if configured. For variable declarations outside methods, removes trailing whitespace after the semicolon and inserts a newline with proper indentation. For declarations inside methods, only spacing around the assignment operator is adjusted.
        """
        parent = ctx.parentCtx 
        parentCopy = parent
        is_method= False
        while parent:
            if isinstance(parent, JavaParser.MethodDeclarationContext):
                is_method= True
                break
            parent = parent.parentCtx  # Move up the tree


        if ctx.ASSIGN():
            assignment = ctx.ASSIGN().symbol
            if assignment:
                if self.config.space_around_operator:
                    prev_token_index = assignment.tokenIndex - 1
                    next_token_index = assignment.tokenIndex + 1

                    # add space before the assignment if needed
                    prev_token = self.rewriter.getTokenStream().get(prev_token_index)
                    if prev_token.type != JavaParser.WS and prev_token.text != " ":
                        self.rewriter.insertBeforeIndex(assignment.tokenIndex, " ")

                    # add space after the assignment if needed
                    next_token = self.rewriter.getTokenStream().get(next_token_index)
                    if next_token.type != JavaParser.WS and next_token.text != " ":
                        self.rewriter.insertAfter(assignment.tokenIndex, " ")
        if is_method:
            return super().visitVariableDeclarator(ctx)
        semi = ctx.stop.tokenIndex
        if hasattr(parentCopy, 'SEMI') and parentCopy.SEMI():
            semi = parentCopy.SEMI().symbol.tokenIndex
        else:
            token_stream = self.rewriter.getTokenStream()
            end = ctx.stop.tokenIndex
            while token_stream and token_stream.get(end).type != JavaParser.SEMI:
                if token_stream.get(end).type in [JavaParser.WS]:
                    self.rewriter.deleteToken(end)
                end +=1
            semi = end
            if token_stream.get(semi+1).type in [JavaParser.WS]:
                self.rewriter.deleteToken(semi+1)


        self.rewriter.insertBeforeIndex(semi+1, f"\n{self._get_indent()}")
            
        return super().visitVariableDeclarator(ctx)

    def visitBinaryOperatorExpression(self, ctx: JavaParser.BinaryOperatorExpressionContext):
        """
        Ensures proper spacing around binary operators in expressions.
        
        If the configuration enables spacing around operators, inserts a space before and after each binary operator in the expression as needed.
        """
        if self.config.space_around_operator and ctx.bop:

            # get operator token
            operator = ctx.bop

            prev_token_index = operator.tokenIndex - 1
            next_token_index = operator.tokenIndex + 1

            # add space before the operator if needed
            prev_token = self.rewriter.getTokenStream().get(prev_token_index)
            if prev_token.type != JavaParser.WS and prev_token.text != " ":
                self.rewriter.insertBeforeIndex(operator.tokenIndex, " ")

            # add space after the operator if needed
            next_token = self.rewriter.getTokenStream().get(next_token_index)
            if next_token.type != JavaParser.WS and next_token.text != " ":
                self.rewriter.insertAfter(operator.tokenIndex, " ")

        return self.visitChildren(ctx)

    def visitUnaryOperatorExpression(self, ctx: JavaParser.UnaryOperatorExpressionContext):
        if self.config.space_around_operator:
            # fore prefix operator 
            if hasattr(ctx, 'prefix') and ctx.prefix:
                next_token_index = ctx.prefix.tokenIndex + 1
                next_token = self.rewriter.getTokenStream().get(next_token_index)

                # don't add space after `++` or `--`
                if ctx.prefix.type not in [JavaParser.INC, JavaParser.DEC]:
                    if next_token.type != JavaParser.WS and next_token.text != " ":
                        self.rewriter.insertAfter(ctx.prefix.tokenIndex, " ")
        return self.visitChildren(ctx)

    def visitLambdaExpression(self, ctx: JavaParser.LambdaExpressionContext):
        if self.config.space_around_operator:
            arrow = ctx.ARROW().symbol
            prev_token_index = arrow.tokenIndex - 1
            next_token_index = arrow.tokenIndex + 1

            # add space before the arrow if needed
            prev_token = self.rewriter.getTokenStream().get(prev_token_index)
            if prev_token.type != JavaParser.WS and prev_token.text != " ":
                self.rewriter.insertBeforeIndex(arrow.tokenIndex, " ")

            # add space after the arrow if needed
            next_token = self.rewriter.getTokenStream().get(next_token_index)
            if next_token.type != JavaParser.WS and next_token.text != " ":
                self.rewriter.insertAfter(arrow.tokenIndex, " ")
        return self.visitChildren(ctx)

    def visitMethodReferenceExpression(self, ctx: JavaParser.MethodReferenceExpressionContext):
        if self.config.space_around_operator:
            double_colon = ctx.COLONCOLON().symbol
            prev_token_index = double_colon.tokenIndex - 1
            next_token_index = double_colon.tokenIndex + 1

            # add space before the double colon if needed
            prev_token = self.rewriter.getTokenStream().get(prev_token_index)
            if prev_token.type != JavaParser.WS and prev_token.text != " ":
                self.rewriter.insertBeforeIndex(double_colon.tokenIndex, " ")

            # add space after the double colon if needed
            next_token = self.rewriter.getTokenStream().get(next_token_index)
            if next_token.type != JavaParser.WS and next_token.text != " ":
                self.rewriter.insertAfter(double_colon.tokenIndex, " ")
        return self.visitChildren(ctx)

    def get_formatted_code(self, tree):
        self.imports = {
            'items': [],
            'start_index': -1,
            'end_index': -1
        }

        self.visit(tree)


        if self.config.imports['order'] == "sort":
            self._order_imports()

            
        formatted_text: str = self.rewriter.getDefaultText()
        return formatted_text
