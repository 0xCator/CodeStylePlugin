from antlr4 import *
from CodeStyle.JavaLexer import JavaLexer
from CodeStyle.JavaParser import JavaParser
from CodeStyle.FormattingVisitor import FormattingVisitor
from CodeStyle.AlignmentVisitor import AlignmentVisitor
from CodeStyle.ErrorLogger import ErrorLogger
from CodeStyle.ConfigClass import ConfigClass
import re

def load_config(config_path):
    config = ConfigClass(config_path)
    return config

def parse_java_code(code):
    lexer = JavaLexer(InputStream(code))
    tokens = CommonTokenStream(lexer)
    parser = JavaParser(tokens)
    tree = parser.compilationUnit()

    return tree, tokens

def clean_code(code):
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
    
    # Now clean the code
    cleaned_code = re.sub(r'[\t\n\r]+', '', code)
    cleaned_code = re.sub(r' {2,}', ' ', cleaned_code)
    cleaned_code = re.sub(r'^ +', '', cleaned_code, flags=re.M)

    return cleaned_code


def restore_line_comments(code):
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

def format_code(tree, tokens, configs):
    formatter = FormattingVisitor(tokens, configs)
    first_code_pass = formatter.get_formatted_code(tree)
    
    lexer = JavaLexer(InputStream(first_code_pass))
    tokens = CommonTokenStream(lexer)
    parser = JavaParser(tokens)
    tree = parser.compilationUnit()

    aligner = AlignmentVisitor(tokens, configs)
    second_code_pass = aligner.get_formatted_code(tree)

    return second_code_pass

def get_errors(tree, configs):
    error_visitor = ErrorLogger(configs)
    errors = error_visitor.find_errors(tree)
    return errors

def start_formatting(code, settings=None):
    configs = ConfigClass(settings)
    code = clean_code(code)
    tree, tokens = parse_java_code(code)
    formatted_code = format_code(tree, tokens, configs)
    formatted_code = restore_line_comments(formatted_code)

    new_tree, new_tokens = parse_java_code(formatted_code)
    errors = get_errors(new_tree, configs)

    return formatted_code, errors
