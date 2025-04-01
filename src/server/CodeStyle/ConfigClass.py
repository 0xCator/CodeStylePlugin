class ConfigClass:
    def __init__(self, config_dict):
        self.config_dict = config_dict

        self.default_config()

        if config_dict:
            self.parse_config()

    def default_config(self):
        self.brace_style = 'break'
        self.space_around_operator = True
        self.max_line_length = 100
        self.class_modifier_order = ['public', 'abstract', 'final']
        self.method_modifier_order = ['public', 'static', 'final']
        self.naming_conventions = {
            'class': 'pascalcase',
            'method': 'camelcase',
            'variable': 'camelcase',
            'parameter': 'camelcase',
            'constant': 'uppercase'
        }
        self.imports = {
            'order': 'preserve', # 'preserve' or 'sort'
            'merge': True
        }
        self.indents = {
            'size': 4,
            'type': 'spaces', # 'spaces' or 'tabs'
            'switch_case_labels': 'indent', # 'indent' or 'no_indent'
        }
        self.aligns = {
            'after_open_bracket': 'align', # false, 'align', 'dont_align', 'always_break', 'block_indent'
            'parameters_before_align': 2 # How many parameters before breaking if 'after_open_bracket' is 'align' or 'dont_align'
        }

    def parse_config(self):
        self.brace_style = self.config_dict['braceStyle']
        self.space_around_operator = self.config_dict['spaceAroundOperators']
        self.max_line_length = self.config_dict['maxLineLength']
        self.class_modifier_order = self.config_dict['modifierOrder']['class']
        self.method_modifier_order = self.config_dict['modifierOrder']['method']
        self.naming_conventions = self.config_dict['namingConventions']
        self.imports = self.config_dict['imports']

        self.indents['size'] = self.config_dict['indents']['size']
        self.indents['type'] = self.config_dict['indents']['type']
        self.indents['switch_case_labels'] = self.config_dict['indents']['switchCaseLabels']

        self.aligns['after_open_bracket'] = self.config_dict['aligns']['afterOpenBracket']
        self.aligns['parameters_before_align'] = self.config_dict['aligns']['parametersBeforeAlignment']