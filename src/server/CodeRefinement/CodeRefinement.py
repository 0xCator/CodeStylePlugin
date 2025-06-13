import CodeRefinement.ModelRunner
import os
import re
import logging

logger = logging.getLogger(__name__)

class CodeRefiner:
    def __init__(self):
        MODEL_PATH = "NexusrexDev/CodeGator-Refinement"
        self.model = CodeRefinement.ModelRunner.ModelRunner(MODEL_PATH)

    def clean_code(self, code):
        cleaned_code = re.sub(r'[\t\n\r]+', '', code)
        cleaned_code = re.sub(r' {2,}', ' ', cleaned_code)
        cleaned_code = re.sub(r'^ +', '', cleaned_code, flags=re.M)
        return cleaned_code

    def start_refinement(self, code, prompt):
        cleaned_code = self.clean_code(code)
        refined_code = self.model.run_model(cleaned_code, prompt)
        return refined_code