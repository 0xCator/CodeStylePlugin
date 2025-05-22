import CodeRefinement.ModelRunner
import os
import re
import logging

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "Model")

def clean_code(code):
    cleaned_code = re.sub(r'[\t\n\r]+', '', code)
    cleaned_code = re.sub(r' {2,}', ' ', cleaned_code)
    cleaned_code = re.sub(r'^ +', '', cleaned_code, flags=re.M)

    return cleaned_code

def start_refinement(code, prompt):
    cleaned_code = clean_code(code)
    model = CodeRefinement.ModelRunner.ModelRunner(MODEL_PATH)
    refined_code = model.run_model(cleaned_code, prompt)
    return refined_code