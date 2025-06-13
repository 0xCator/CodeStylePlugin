from antlr4 import *
from torch.distributions import continuous_bernoulli
from CodeStyle.JavaLexer import JavaLexer
from CodeStyle.JavaParser import JavaParser
from CodeStyle.FormattingVisitor import FormattingVisitor
from CodeStyle.AlignmentVisitor import AlignmentVisitor
from CodeStyle.ErrorLogger import ErrorLogger
from CodeStyle.ConfigClass import ConfigClass
import re

class CodeStyleFormatter:
    def __init__(self, config_path=None):
        self.configs = ConfigClass(config_path) if config_path else None

    def load_config(self, config_path):
        self.configs = ConfigClass(config_path)
        return self.configs

    def parse_java_code(self, code):
        lexer = JavaLexer(InputStream(code))
        tokens = CommonTokenStream(lexer)
        parser = JavaParser(tokens)
        tree = parser.compilationUnit()
        return tree, tokens

    def clean_code(self, code):
        # Convert line comments to block comments with a special marker
        def convert_line_to_block(match):
            comment = match.group(0)
            # Remove the // and convert to block comment format
            comment_text = comment[2:].strip()
            # Escape any '*/' sequences in the comment text
            comment_text = comment_text.replace('*/', '*\\/')
            return f"/* LINE_COMMENT: {comment_text} */"

        # Replace line comments with block comments
        code = re.sub(r'//[^\n]*', convert_line_to_block, code)
        
        # Split the code into comments and non-comments
        parts = []
        current_pos = 0
        for match in re.finditer(r'/\*.*?\*/', code, re.DOTALL):
            # Get the code before the comment
            if match.start() > current_pos:
                code_part = code[current_pos:match.start()]
                # Extract hidden tokens (newlines and spaces) before the comment
                hidden_tokens = re.search(r'[\n\r][ \t]*$', code_part)
                hidden_before = hidden_tokens.group(0) if hidden_tokens else ''
                
                # Calculate indentation level from the code structure
                indent_level = 0
                if hidden_before:
                    # Get the code before the last newline
                    code_before_newline = code_part[:match.start() - len(hidden_before)]
                    # Count opening and closing braces to determine nesting level
                    # Only count braces that are not inside string literals or comments
                    brace_count = 0
                    in_string = False
                    in_char = False
                    escape_next = False
                    
                    for char in code_before_newline:
                        if escape_next:
                            escape_next = False
                            continue
                            
                        if char == '\\':
                            escape_next = True
                            continue
                            
                        if char == '"' and not in_char:
                            in_string = not in_string
                            continue
                            
                        if char == "'" and not in_string:
                            in_char = not in_char
                            continue
                            
                        if not in_string and not in_char:
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                    
                    indent_level = max(0, brace_count)
                
                # Clean the code part without the hidden tokens
                code_part = code_part[:match.start() - len(hidden_before)]
                code_part = re.sub(r'[\t\n\r]+', '', code_part)
                code_part = re.sub(r' {2,}', ' ', code_part)
                code_part = re.sub(r'^ +', '', code_part, flags=re.M)
                
                # Add the cleaned code
                parts.append(code_part)
                
                if hidden_before:
                    # Split by newlines and rejoin with proper indentation
                    lines = hidden_before.split('\n')
                    indented_lines = []
                    indent_level = indent_level+1 if 'LINE_COMMENT:' in match.group(0) else indent_level
                    for i, line in enumerate(lines):
                        if i == len(lines) - 1:  # Last line (before comment)
                            if self.configs.indents['type'] == 'spaces':
                                indented_lines.append(' ' * (indent_level  * self.configs.indents['size']))
                            else:  # tabs
                                indented_lines.append('\t' * indent_level )
                        else:
                            indented_lines.append(line)
                    parts.append('\n'.join(indented_lines))
            
            # comment block (the original one)
            comment = match.group(0)
            if 'LINE_COMMENT:' not in comment:
                # This is a regular block comment, ensure consistent indentation
                comment_lines = comment.split('\n')
                indented_comment_lines = []
                
                # Calculate base indentation for the comment block
                if self.configs.indents['type'] == 'spaces':
                    base_indent = ' ' * (indent_level * self.configs.indents['size'])
                else:  # tabs
                    base_indent = '\t' * indent_level
                
                base_indent += ' '
                for i, line in enumerate(comment_lines):
                    if i == 0:  # First line with /*
                        indented_comment_lines.append(line.strip())
                    elif i == len(comment_lines) - 1:  # Last line with */
                        indented_comment_lines.append(base_indent + line.strip())
                    else:  # Middle lines
                        indented_comment_lines.append(base_indent + line.strip())
                
                comment = '\n'.join(indented_comment_lines)
            
            parts.append(comment)
            current_pos = match.end()
        
        # Add any remaining code
        if current_pos < len(code):
            remaining_code = code[current_pos:]
            remaining_code = re.sub(r'[\t\n\r]+', '', remaining_code)
            remaining_code = re.sub(r' {2,}', ' ', remaining_code)
            remaining_code = re.sub(r'^ +', '', remaining_code, flags=re.M)
            parts.append(remaining_code)

        return ''.join(parts)

    def restore_line_comments(self, code):
        # Convert block comments back to line comments
        def convert_block_to_line(match):
            comment = match.group(0)
            # Extract the comment text and convert it back to line comment format
            comment_text = comment[2:-2].strip()  # Remove /* and */
            # Remove 'LINE_COMMENT:' prefix without adding extra space
            comment_text = comment_text.replace('LINE_COMMENT:', '', 1).strip()
            # Unescape any '*/' sequences in the comment text
            comment_text = comment_text.replace('*\\/', '*/')
            return f"//{comment_text}"

        # Replace block comments with line comments using non-greedy match
        restored_code = re.sub(r'/\* LINE_COMMENT: .*?\*/', convert_block_to_line, code, flags=re.DOTALL)

        return restored_code

    def format_code(self, tree, tokens):
        formatter = FormattingVisitor(tokens, self.configs)
        first_code_pass = formatter.get_formatted_code(tree)

        lexer = JavaLexer(InputStream(first_code_pass))
        tokens = CommonTokenStream(lexer)
        parser = JavaParser(tokens)
        tree = parser.compilationUnit()

        aligner = AlignmentVisitor(tokens, self.configs)
        second_code_pass = aligner.get_formatted_code(tree)

        return second_code_pass

    def get_errors(self, tree):
        error_visitor = ErrorLogger(self.configs)
        errors = error_visitor.find_errors(tree)
        return errors

    def start_formatting(self, code, settings=None):
        if settings:
            self.configs = ConfigClass(settings)
        code = self.clean_code(code)
        tree, tokens = self.parse_java_code(code)
        formatted_code = self.format_code(tree, tokens)
        formatted_code = self.restore_line_comments(formatted_code)

        new_tree, new_tokens = self.parse_java_code(formatted_code)
        errors = self.get_errors(new_tree)

        return formatted_code, errors