from typing import Optional
from CodeStyle.JavaParser import JavaParser
from CodeStyle.JavaParserVisitor import JavaParserVisitor
from antlr4.TokenStreamRewriter import TokenStreamRewriter
from antlr4.Token import CommonToken
from functools import wraps
from CodeStyle.ConfigClass import ConfigClass

class AlignmentVisitor(JavaParserVisitor):
    def __init__(self, tokens, config: ConfigClass):
        self.rewriter : TokenStreamRewriter = TokenStreamRewriter(tokens)
        self.config:ConfigClass = config
        self.indent_level: int = 0
    
    def _apply_max_line_length_line(self, line: str) -> str:
        if len(line) <= self.config.max_line_length:
            return line

        indent = ''
        for char in line:
            if char == " " or char == "\t":
                indent += char
            else:
                break

        if '"' in line or "'" in line:
            in_string = False
            string_type = None
            string_positions = []
            string_start = -1

            for i, char in enumerate(line):
                if not in_string and (char == '"' or char == "'"):
                    in_string = True
                    string_type = char
                    string_start = i
                elif in_string and char == string_type and line[i-1] != '\\':
                    in_string = False
                    string_positions.append((string_start, i))

            if in_string:
                string_positions.append((string_start, len(line) - 1))

            if string_positions:
                start, end = string_positions[0]
                before_string = line[:start]
                string_literal = line[start:end+1]
                after_string = line[end+1:]

                if len(string_literal) > self.config.max_line_length:
                    string_content = string_literal[1:-1]  # Remove quotes
                    split_strings = []
                    current_part = ''

                    for word in string_content.split(" "):
                        if len(before_string) + len(current_part.strip()) + len(word) + 3 > self.config.max_line_length:  # 3 accounts for '" + "'
                            split_strings.append(current_part)
                            current_part = word
                        else:
                            if current_part:
                                current_part += ' '
                            current_part += word

                    if current_part:
                        split_strings.append(current_part)

                    formatted_string = f'{string_type}\n {indent}    + {string_type}'.join(split_strings)
                    new_line = f"{before_string}{string_type}{formatted_string}{string_type}{after_string}"
                    return new_line

        line = line[len(indent):]
        words = line.split(" ")
        new_line = ''
        current_line = ''
        for word in words:
            if len(current_line) + len(word) > self.config.max_line_length:
                new_line += current_line + "\n" + indent
                current_line = word + " "
            else:
                current_line += word + " "
        new_line += current_line.strip()
        return indent + new_line

    def _apply_max_line_length(self, text: str) -> str:
        if self.config.max_line_length == -1:
            return text
        return "\n".join([self._apply_max_line_length_line(line) for line in text.split("\n")])

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
        return self.visitChildren(ctx)
    
    @handle_indentation
    def visitSwitchBlockStatementGroup(self, ctx: JavaParser.SwitchBlockStatementGroupContext):
        return self.visitChildren(ctx)
    
    def visitClassDeclaration(self, ctx):
        if ctx.classBody():
            self.indent_level += 1
        return self.visitChildren(ctx)

    def visitMethodDeclaration(self, ctx):
        arguments : JavaParser.formalParameters = ctx.formalParameters()

        if arguments:
            open_paren = arguments.LPAREN().getSymbol()
            close_paren = arguments.RPAREN().getSymbol()
            parameters = arguments.formalParameterList()
            if parameters:
                parameter_size = int((parameters.getChildCount() + 1) / 2)

                if parameter_size > 1 and self.config.aligns['after_open_bracket'] != False:
                    self._apply_bracket_alignment(open_paren, parameters, close_paren, parameter_size)

        return self.visitChildren(ctx)

    def visitMethodCall(self, ctx: JavaParser.MethodCallContext):
        arguments : JavaParser.ArgumentsContext = ctx.arguments()
        if arguments:
            open_paren : CommonToken = arguments.LPAREN().getSymbol()
            close_paren : CommonToken = arguments.RPAREN().getSymbol()
            parameters : JavaParser.ExpressionListContext = arguments.expressionList()
            if not parameters:
                return self.visitChildren(ctx)
            
            parameter_size = int((parameters.getChildCount() + 1) / 2) # Getting the actual number of parameters
            
            if parameter_size > 1 and self.config.aligns['after_open_bracket'] != False:
                self._apply_bracket_alignment(open_paren, parameters, close_paren, parameter_size)

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
        while token_stream.get(token_index).line == open_paren.line:
            spacer_length += len(token_stream.get(token_index).text)
            token_index -= 1

        return " " * (spacer_length + (self.indent_level * self.config.indents['size']))   

    def _get_indent(self):
        match self.config.indents['type']:
            case "spaces":
                return " " * (self.indent_level * self.config.indents['size'])
            # may it appear as 8 spaces but it is actually configurable
            # in text editors so it should be as a size of indent_size
            case "tabs":
                return "\t" * self.indent_level
    
    def get_formatted_code(self, tree):
        self.visit(tree)

        formatted_code = self.rewriter.getDefaultText()
        return self._apply_max_line_length(formatted_code)