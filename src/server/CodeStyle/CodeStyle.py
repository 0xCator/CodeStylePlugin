from antlr4 import *
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
        cleaned_code = re.sub(r'[\t\n\r]+', '', code)
        cleaned_code = re.sub(r' {2,}', ' ', cleaned_code)
        cleaned_code = re.sub(r'^ +', '', cleaned_code, flags=re.M)
        return cleaned_code

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

        new_tree, new_tokens = self.parse_java_code(formatted_code)
        errors = self.get_errors(new_tree)

        return formatted_code, errors