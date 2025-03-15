from CodeStyle.JavaParser import JavaParser
from CodeStyle.JavaParserVisitor import JavaParserVisitor
from CodeStyle.StandardNamingConventions import StandardNamingConventions
from CodeStyle.ConfigClass import ConfigClass
import re

class ErrorLogger(JavaParserVisitor):
    def __init__(self, configs: ConfigClass):
        self.configs = configs
        self.error_log = []

    def visitClassDeclaration(self, ctx: JavaParser.ClassDeclarationContext):
        class_name = ctx.identifier().getText()
        class_config = self.configs.naming_conventions["class"]
        error = self.check_convention(class_name, class_config)
        if error:
            position_text = f"Line {ctx.identifier().start.line}, Column {ctx.identifier().start.column}:"
            self.error_log.append(position_text + "Class " + error)


        return self.visitChildren(ctx)

    def visitMethodDeclaration(self, ctx: JavaParser.MethodDeclarationContext):
        method_name = ctx.identifier().getText()

        method_config = self.configs.naming_conventions["method"]
        error = self.check_convention(method_name, method_config)

        if error:
            position_text = f"Line {ctx.identifier().start.line}, Column {ctx.identifier().start.column}:"
            self.error_log.append(position_text + "Method " + error)


        return self.visitChildren(ctx)

    def visitFieldDeclaration(self, ctx: JavaParser.FieldDeclarationContext):
        declarators = ctx.variableDeclarators()
        modifiers = [mod.getText() for mod in ctx.parentCtx.parentCtx.modifier()]
        is_static = "static" in modifiers
        is_final = "final" in modifiers

        variable_config = self.configs.naming_conventions["variable"]
        constant_config = self.configs.naming_conventions["constant"]

        for declarator in declarators.variableDeclarator():
            field_name = declarator.variableDeclaratorId().getText()

            error = None

            if is_static and is_final:
                error = self.check_convention(field_name, constant_config)
            else:
                error = self.check_convention(field_name, variable_config)

            if error:
                position_text = f"Line {declarator.variableDeclaratorId().start.line}, Column {declarator.variableDeclaratorId().start.column}:"
                self.error_log.append(position_text + "Field " + error)


        return self.visitChildren(ctx)

    def visitLocalVariableDeclaration(self, ctx: JavaParser.LocalVariableDeclarationContext):
        declarators = ctx.variableDeclarators()

        variable_config = self.configs.naming_conventions["variable"]

        for declarator in declarators.variableDeclarator():
            variable_name = declarator.variableDeclaratorId().getText()

            error = self.check_convention(variable_name, variable_config)
            if error:
                position_text = f"Line {declarator.variableDeclaratorId().start.line}, Column {declarator.variableDeclaratorId().start.column}:"
                self.error_log.append(position_text + "Local variable " + error)


        return self.visitChildren(ctx)

    def visitFormalParameter(self, ctx: JavaParser.FormalParameterContext):
        parameter_name = ctx.variableDeclaratorId().getText()

        parameter_config = self.configs.naming_conventions["parameter"]

        error = self.check_convention(parameter_name, parameter_config)
        if error:
            position_text = f"Line {ctx.variableDeclaratorId().start.line}, Column {ctx.variableDeclaratorId().start.column}:"
            self.error_log.append(position_text + "Parameter " + error)


        return self.visitChildren(ctx)

    @staticmethod
    def check_convention(name, convention) -> bool:
        patterns = {
            StandardNamingConventions.PASCAL_CASE.value: r"[A-Z][a-zA-Z0-9]*",
            StandardNamingConventions.CAMEL_CASE.value: r"[a-z][a-zA-Z0-9]*",
            StandardNamingConventions.UPPER_CASE.value: r"[A-Z][A-Z0-9_]*"
        }

        pattern = patterns.get(convention, convention)

        if not bool(re.fullmatch(pattern, name)):
            return f"'{name}' does not match the naming convention '{convention}'"

        return None

    def find_errors(self, tree) -> list:
        self.error_log = []
        self.visit(tree)
        return self.error_log