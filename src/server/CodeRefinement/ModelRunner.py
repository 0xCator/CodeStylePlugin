from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

class ModelRunner:
    def __init__(self, model_name):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run_model(self, text, prompt):
        if self.cancelled:
            raise Exception("Analysis cancelled")
        
        text = f"refine: {prompt} <sep> {text}"

        encoding = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
        encoding = {k: v.to(self.model.device) for k,v in encoding.items()}

        if self.cancelled:
            raise Exception("Analysis cancelled")

        output = self.model.generate(**encoding, max_length=512, num_beams=1, do_sample=False, use_cache=True)

        if self.cancelled:
            raise Exception("Analysis cancelled")

        decoded_output = self.tokenizer.decode(output[0], skip_special_tokens=True)

        return decoded_output