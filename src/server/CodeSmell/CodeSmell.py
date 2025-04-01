import CodeSmell.classparser
import CodeSmell.modelrunner
import numpy as np
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "Model\\")

def start_analysis(code, progress_callback=None):
    total_smells = []

    parser = CodeSmell.classparser.ClassParser(code)
    methods = parser.get_full_methods()
    prototypes = parser.get_method_prototypes()
    formatted_code = parser.code

    model = CodeSmell.modelrunner.ModelRunner(MODEL_PATH)

    total_progress = len(methods) + len(prototypes) + 1
    current_progress = 0

    total_smells.append(model.run_model(formatted_code))
    current_progress += 1

    if progress_callback:
        progress_callback(int(current_progress / total_progress * 100))

    for method in methods:
        total_smells.append(model.run_model(method))
        current_progress += 1

        if progress_callback:
            progress_callback(int(current_progress / total_progress * 100))

    for prototype in prototypes:
        total_smells.append(model.run_model(prototype))
        current_progress += 1

        if progress_callback:
            progress_callback(int(current_progress / total_progress * 100))
    
    total_smells = np.concatenate(total_smells)
    total_smells = np.unique(total_smells)

    return total_smells.tolist()