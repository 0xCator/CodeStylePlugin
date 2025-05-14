import CodeSmell.classparser
import CodeSmell.modelrunner
import numpy as np
import os
from collections import defaultdict

MODEL_PATH = os.path.join(os.path.dirname(__file__), "Model")

def start_analysis(code, progress_callback=None):
    total_smells: defaultdict = defaultdict(list)

    parser = CodeSmell.classparser.ClassParser(code)
    methods = parser.get_full_methods()
    prototypes = parser.get_method_prototypes()
    formatted_code = parser.code

    model = CodeSmell.modelrunner.ModelRunner(MODEL_PATH)

    total_progress = len(methods) + len(prototypes) + 1
    current_progress = 0

    try:
        # Entire class scan
        class_smells = model.run_model(formatted_code)
        # Add class smells to the dictionary with the key 'class'
        total_smells.setdefault('class', [])
        total_smells['class'].append(class_smells)
        total_smells['class'] = np.concatenate(total_smells['class'])
        total_smells['class'] = np.unique(total_smells['class'])
        total_smells['class'] = total_smells['class'].tolist()

        current_progress += 1

        if progress_callback:
            try:
                progress_callback(int(current_progress / total_progress * 100))
            except Exception as e:
                if str(e) == "Analysis cancelled":
                    model.cancel()  # Signal model to stop
                    return {}  # Return empty dictionary if cancelled

        for index, method in enumerate(methods):
            method_smells = model.run_model(method)
            total_smells.setdefault(f'{prototypes[index]}', [])
            total_smells[f'{prototypes[index]}'].append(method_smells)
            current_progress += 1

            if progress_callback:
                try:
                    progress_callback(int(current_progress / total_progress * 100))
                except Exception as e:
                    if str(e) == "Analysis cancelled":
                        model.cancel()  # Signal model to stop
                        return {}  # Return empty dictionary if cancelled

        for prototype in prototypes:
            prototype_smells = model.run_model(prototype)
            total_smells.setdefault(f'{prototype}', [])
            total_smells[f'{prototype}'].append(prototype_smells)
            total_smells[f'{prototype}'] = np.concatenate(total_smells[f'{prototype}'])
            total_smells[f'{prototype}'] = np.unique(total_smells[f'{prototype}'])
            total_smells[f'{prototype}'] = total_smells[f'{prototype}'].tolist()
            current_progress += 1

            if progress_callback:
                try:
                    progress_callback(int(current_progress / total_progress * 100))
                except Exception as e:
                    if str(e) == "Analysis cancelled":
                        model.cancel()  # Signal model to stop
                        return {}  # Return empty dictionary if cancelled

        return total_smells
    except Exception as e:
        if str(e) == "Analysis cancelled":
            return {}
        raise e
