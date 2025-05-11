from antlr4 import *
from CodeStyle.JavaLexer import JavaLexer
from CodeStyle.JavaParser import JavaParser
from CodeStyle.FormattingVisitor import FormattingVisitor
from CodeStyle.AlignmentVisitor import AlignmentVisitor
from CodeStyle.CommentVisitor import CommentVisitor
from CodeStyle.ErrorLogger import ErrorLogger
from CodeStyle.ConfigClass import ConfigClass
import re

def load_config(config_path):
    config = ConfigClass(config_path)
    return config

def parse_java_code(code):
    input_stream = InputStream(code)
    lexer = JavaLexer(input_stream)
    stream = CommonTokenStream(lexer)
    stream.fill()  # Fill the token stream
    parser = JavaParser(stream)
    tree = parser.compilationUnit()
    return tree, stream

def clean_code(code):
    """Clean the code while preserving essential whitespace."""
    # Split into lines and process each line
    lines = code.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Remove trailing whitespace
        line = line.rstrip()
        # Replace multiple spaces with single space, except in indentation
        indent = ''
        content = line.lstrip()
        if line:
            indent = line[:-len(content)] if content else line
        
        # Clean the content part
        content = re.sub(r' {2,}', ' ', content)
        
        # Combine indent and content
        cleaned_line = indent + content
        cleaned_lines.append(cleaned_line)
    
    return '\n'.join(cleaned_lines)

def format_code(tree, tokens, configs):
    try:
        # First pass: Extract comments
        comment_formatter = CommentVisitor(tokens, configs)
        comment_formatter.extract_comments()
        code_without_comments = comment_formatter.get_formatted_code(tree)
        
        if not code_without_comments.strip():
            return ""  # Return empty string if no code remains after comment extraction
        
        # Second pass: Basic formatting
        tree, tokens = parse_java_code(code_without_comments)
        formatter = FormattingVisitor(tokens, configs)
        formatted_code = formatter.get_formatted_code(tree)
        
        # Third pass: Alignment
        tree, tokens = parse_java_code(formatted_code)
        aligner = AlignmentVisitor(tokens, configs)
        aligned_code = aligner.get_formatted_code(tree)
        
        # Final pass: Restore formatted comments
        final_code = comment_formatter.restore_comments(aligned_code)
        return final_code
        
    except Exception as e:
        print(f"Error during formatting: {str(e)}")
        return tokens.getText()

def get_errors(tree, configs):
    error_visitor = ErrorLogger(configs)
    errors = error_visitor.find_errors(tree)
    return errors

def start_formatting(code, settings=None):
    try:
        configs = ConfigClass(settings)
        tree, tokens = parse_java_code(code)
        formatted_code = format_code(tree, tokens, configs)

        if formatted_code:
            new_tree, new_tokens = parse_java_code(formatted_code)
            errors = get_errors(new_tree, configs)
        else:
            errors = []

        return formatted_code, errors
    except Exception as e:
        print(f"Error in start_formatting: {str(e)}")
        return code, []  # Return original code if formatting fails