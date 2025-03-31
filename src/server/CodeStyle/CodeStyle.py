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
    cleaned_code = re.sub(r'[\t\n\r]+', '', code)
    cleaned_code = re.sub(r' {2,}', ' ', cleaned_code)
    cleaned_code = re.sub(r'^ +', '', cleaned_code, flags=re.M)

    return cleaned_code

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

    new_tree, new_tokens = parse_java_code(formatted_code)
    errors = get_errors(new_tree, configs)

    return formatted_code, errors