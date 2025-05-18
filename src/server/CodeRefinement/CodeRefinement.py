from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import os
import re

MODEL_PATH = os.path.join(os.path.dirname(__file__), "Model")

def clean_code(code):
    cleaned_code = re.sub(r'[\t\n\r]+', '', code)
    cleaned_code = re.sub(r' {2,}', ' ', cleaned_code)
    cleaned_code = re.sub(r'^ +', '', cleaned_code, flags=re.M)

    return cleaned_code

def start_refinement(code, settings=None):
    code = clean_code(code)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_PATH)

    inputs = tokenizer(code, return_tensors="pt", max_length=512, truncation=True, padding='max_length')
    outputs = model.generate(**inputs, max_length=512, num_beams=1, do_sample=False, use_cache=True)

    refined_code = tokenizer.decode(outputs[0], skip_special_tokens=True)

    return refined_code