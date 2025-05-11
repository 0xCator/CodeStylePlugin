from typing import Optional, List, Tuple, Dict
from CodeStyle.JavaParser import JavaParser
from CodeStyle.JavaParserVisitor import JavaParserVisitor
from antlr4.TokenStreamRewriter import TokenStreamRewriter
from antlr4.Token import CommonToken
from CodeStyle.ConfigClass import ConfigClass

class CommentVisitor(JavaParserVisitor):
    def __init__(self, tokens, config: ConfigClass):
        self.rewriter: TokenStreamRewriter = TokenStreamRewriter(tokens)
        self.config: ConfigClass = config
        self.token_stream = tokens
        self.indent_level: int = 0
        self.last_token: Optional[CommonToken] = None
        # Store comments with their context: (line_number, column, text, is_block_comment, preceding_token_type, following_token_type, original_indent)
        self.comments: List[Tuple[int, int, str, bool, int, int, str]] = []
        # Store comment positions relative to code elements
        self.comment_positions: Dict[int, Dict] = {}

    def _get_indent(self):
        match self.config.indents['type']:
            case "spaces":
                return " " * (self.indent_level * self.config.indents['size'])
            case "tabs":
                return "\t" * self.indent_level

    def _format_block_comment(self, comment_text: str, original_indent: str = "") -> str:
        """Format a block comment with proper indentation and line wrapping."""
        lines = comment_text.split('\n')
        formatted_lines = []
        
        # Use original indentation if available, otherwise use calculated indent
        indent = original_indent if original_indent else self._get_indent()
        
        # Format first line
        first_line = lines[0].strip()
        if not first_line.startswith('/*'):
            first_line = '/* ' + first_line
        formatted_lines.append(indent + first_line)
        
        # Format middle lines
        for line in lines[1:-1]:
            stripped = line.strip()
            if stripped:
                if not stripped.startswith('*'):
                    stripped = '* ' + stripped
                formatted_lines.append(indent + ' ' + stripped)
            else:
                formatted_lines.append(indent + ' *')
        
        # Format last line
        if len(lines) > 1:
            last_line = lines[-1].strip()
            if not last_line.endswith('*/'):
                last_line = last_line + ' */'
            if not last_line.startswith('*'):
                last_line = '* ' + last_line
            formatted_lines.append(indent + ' ' + last_line)
        elif not first_line.endswith('*/'):
            formatted_lines[-1] = formatted_lines[-1] + ' */'
            
        return '\n'.join(formatted_lines)

    def _format_line_comment(self, comment_text: str, original_indent: str = "") -> str:
        """Format a single-line comment with proper indentation."""
        # Use original indentation if available, otherwise use calculated indent
        indent = original_indent if original_indent else self._get_indent()
        
        # Clean up the comment text
        comment_text = comment_text.strip()
        if not comment_text.startswith('//'):
            comment_text = '// ' + comment_text
        else:
            # Ensure exactly one space after //
            comment_text = '// ' + comment_text[2:].lstrip()
            
        return indent + comment_text

    def _wrap_comment_if_needed(self, comment: str, is_block: bool) -> str:
        """Wrap comment text if it exceeds max line length."""
        if not self.config.comments['wrap_comments'] or self.config.max_line_length <= 0:
            return comment
            
        lines = comment.split('\n')
        wrapped_lines = []
        
        for line in lines:
            if len(line) <= self.config.max_line_length:
                wrapped_lines.append(line)
                continue
                
            # Preserve original indentation
            indent = ''
            for char in line:
                if char in [' ', '\t']:
                    indent += char
                else:
                    break
                    
            words = line[len(indent):].split()
            current_line = indent
            
            if is_block:
                if not line.strip().startswith('*'):
                    current_line += '* '
            else:
                if not line.strip().startswith('//'):
                    current_line += '// '
                    
            for word in words:
                if len(current_line) + len(word) + 1 > self.config.max_line_length:
                    wrapped_lines.append(current_line)
                    current_line = indent
                    if is_block:
                        current_line += '* '
                    else:
                        current_line += '// '
                    current_line += word
                else:
                    if current_line.endswith('* ') or current_line.endswith('// '):
                        current_line += word
                    else:
                        current_line += ' ' + word
                        
            if current_line:
                wrapped_lines.append(current_line)
                
        return '\n'.join(wrapped_lines)

    def extract_comments(self):
        """Extract all comments and their context from the token stream."""
        self.comments.clear()
        self.comment_positions.clear()
        
        # Get total number of tokens
        total_tokens = self.token_stream.getNumberOfOnChannelTokens()
        current_token_index = 0
        
        while current_token_index < total_tokens:
            token = self.token_stream.LT(current_token_index + 1)  # ANTLR4 uses 1-based indexing for LT
            if token and token.type in [JavaParser.COMMENT, JavaParser.LINE_COMMENT]:
                # Get preceding and following tokens
                preceding_token = self.token_stream.LT(current_token_index) if current_token_index > 0 else None
                following_token = self.token_stream.LT(current_token_index + 2) if current_token_index < total_tokens - 1 else None
                
                preceding_type = preceding_token.type if preceding_token else -1
                following_type = following_token.type if following_token else -1
                
                # Extract original indentation
                original_indent = ''
                token_text = token.text
                token_start = token.start
                while token_start > 0 and token_text[0] in [' ', '\t']:
                    original_indent += token_text[0]
                    token_text = token_text[1:]
                    token_start -= 1
                
                self.comments.append((
                    token.line,
                    token.column,
                    token_text,
                    token.type == JavaParser.COMMENT,
                    preceding_type,
                    following_type,
                    original_indent
                ))
                
                # Store comment position relative to code
                self.comment_positions[current_token_index] = {
                    'line': token.line,
                    'column': token.column,
                    'preceding_type': preceding_type,
                    'following_type': following_type,
                    'original_indent': original_indent
                }
                
                # Remove comment from token stream
                self.rewriter.delete(token)
            
            current_token_index += 1

    def restore_comments(self, formatted_code: str) -> str:
        """Restore formatted comments to their appropriate positions in the code."""
        if not formatted_code:
            return formatted_code
            
        lines = formatted_code.split('\n')
        result_lines = []
        current_line = 1
        
        # Sort comments by line and column
        sorted_comments = sorted(self.comments, key=lambda x: (x[0], x[1]))
        
        for line in lines:
            # Add any comments that should appear before this line
            while sorted_comments and sorted_comments[0][0] == current_line:
                comment = sorted_comments.pop(0)
                # Use original indentation if available
                if comment[6]:  # original_indent
                    formatted = (self._format_block_comment(comment[2], comment[6]) if comment[3]
                               else self._format_line_comment(comment[2], comment[6]))
                else:
                    # Calculate indent based on the current line
                    indent_level = len(line) - len(line.lstrip()) // max(self.config.indents['size'], 1)
                    self.indent_level = indent_level
                    formatted = (self._format_block_comment(comment[2]) if comment[3]
                               else self._format_line_comment(comment[2]))
                
                if self.config.comments['wrap_comments']:
                    formatted = self._wrap_comment_if_needed(formatted, comment[3])
                
                result_lines.append(formatted)
                
                # Add newline after block comments or before code
                if comment[3] or line.strip():
                    result_lines.append('')
            
            # Add the code line
            if line.strip() or not sorted_comments or sorted_comments[0][0] > current_line + 1:
                result_lines.append(line)
            
            current_line += 1
        
        # Add any remaining comments at the end
        for comment in sorted_comments:
            if comment[6]:  # original_indent
                formatted = (self._format_block_comment(comment[2], comment[6]) if comment[3]
                           else self._format_line_comment(comment[2], comment[6]))
            else:
                formatted = (self._format_block_comment(comment[2]) if comment[3]
                           else self._format_line_comment(comment[2]))
                
            if self.config.comments['wrap_comments']:
                formatted = self._wrap_comment_if_needed(formatted, comment[3])
            
            result_lines.append(formatted)
            result_lines.append('')
        
        # Clean up multiple consecutive empty lines
        final_lines = []
        prev_empty = False
        for line in result_lines:
            if not line.strip():
                if not prev_empty:
                    final_lines.append(line)
                prev_empty = True
            else:
                final_lines.append(line)
                prev_empty = False
        
        return '\n'.join(final_lines)

    def get_formatted_code(self, tree):
        """Process the code and return the formatted version with proper comments."""
        return self.rewriter.getDefaultText() 