from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import numpy as np

class ModelRunner:
    def __init__(self, model_name):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.cancelled = False
    
    def cancel(self):
        self.cancelled = True
    
    def run_model(self, text):
        if self.cancelled:
            self.cancelled = False
            raise Exception("Analysis cancelled")
            
        encoding = self.tokenizer(text, return_tensors="pt", max_length=128, truncation=True, padding='max_length')
        encoding = {k: v.to(self.model.device) for k,v in encoding.items()}

        if self.cancelled:
            self.cancelled = False
            raise Exception("Analysis cancelled")

        output = self.model(**encoding)

        if self.cancelled:
            self.cancelled = False
            raise Exception("Analysis cancelled")

        logits = output.logits

        # apply sigmoid + threshold
        sigmoid = torch.nn.Sigmoid()
        probs = sigmoid(logits.squeeze().cpu())
        predictions = np.zeros(probs.shape)
        predictions[np.where(probs >= 0.5)] = 1

        if self.cancelled:
            self.cancelled = False
            raise Exception("Analysis cancelled")

        labels= ['God Class', 'Data Class', 'Long Method', 'Long Parameter List']
        labels = np.array(labels)
        labels = labels[predictions.astype(bool)]

        return labels.tolist()