import javalang
import re

class ClassParser:
    def __init__(self, code):
        self.code = self.code_cleanup(code)
        self.tree = javalang.parse.parse(self.code)
    
    def code_cleanup(self, code):
        code = '\n'.join([line for line in code.splitlines() if line.strip()])
        code = re.sub(r'^\s*import .*;$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*package .*;$', '', code, flags=re.MULTILINE)
        code = re.sub(r'@\w+(\.\w+)*(\s*\(.*?\))?', '', code, flags=re.DOTALL)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        code = re.sub(r'^\s*\*.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*\*/.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'//.*', '', code)
        code = '\n'.join([line for line in code.splitlines() if line.strip()])

        return code

    def single_line_cleanup(self, code, proto = False):
        java_code = code
        # remove all whitespaces, tabs, and newlines
        cleaned_code = re.sub(r'[\t\n\r]+', '', java_code)  # Remove tabs and newlines
        cleaned_code = re.sub(r' {2,}', ' ', cleaned_code)
        cleaned_code = re.sub(r'^ +', '', cleaned_code, flags=re.M)

        # remove { and ;
        if proto:
            cleaned_code = re.sub(r'{', '', cleaned_code)
            cleaned_code = re.sub(r';', '', cleaned_code)
            cleaned_code = cleaned_code.strip()
        return cleaned_code

    def get_methods(self):
        methods = []
        for _, node in self.tree.filter(javalang.tree.MethodDeclaration):
            methods.append(node)
        return methods
    
    def get_constructors(self):
        constructors = []
        for _, node in self.tree.filter(javalang.tree.ConstructorDeclaration):
            constructors.append(node)
        return constructors
    
    def get_method_prototypes(self):
        methods = self.get_methods()
        constructors = self.get_constructors()
        for constructor in constructors:
            methods.append(constructor)
        prototypes = []
        for method in methods:
            prototype = ''
            split_code = self.code.split('\n')
            for i in range(method.position.line - 1, len(split_code)):
                prototype += split_code[i]
                if '{' in split_code[i]:
                    break
                if ';' in split_code[i]:
                    break
            prototypes.append(self.single_line_cleanup(prototype, proto=True))
        return prototypes
    
    def get_full_methods(self):
        methods = self.get_methods()
        constructors = self.get_constructors()
        for constructor in constructors:
            methods.append(constructor)
        full_methods = []

        for method in methods:
            split_code = self.code.split('\n')
            start_line = method.position.line - 1  # Convert to 0-based index

            # Find the end of the method by tracking braces
            brace_count = 0
            end_line = start_line
            method_started = False
            for i in range(start_line, len(split_code)):
                line = split_code[i]
                brace_count += line.count("{") - line.count("}")
                if "{" in line:
                    method_started = True
                if method_started and brace_count == 0:
                    end_line = i
                    break
    
            # Extract method lines
            full_method = split_code[start_line:end_line + 1]
            full_method = '\n'.join(full_method)
            
            full_methods.append(full_method)
        
        return full_methods