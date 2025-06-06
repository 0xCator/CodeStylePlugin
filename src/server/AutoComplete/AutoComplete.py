from transformers import AutoModelForCausalLM, AutoTokenizer

checkpoint = "bigcode/santacoder"
device = "cuda"

class AutoComplete:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(checkpoint)
        self.model = AutoModelForCausalLM.from_pretrained(checkpoint, trust_remote_code=True).to(device)
    
    def create_prompt(self, context):
        # Create prompt that includes the fields from context: className, methods, fields, compositionMembers, inheritedMembers, interfaces as a java comment
        prompt = "// Class: {}\n".format(context.get("className", ""))
        # Put methods in a comment, single line, separated by commas
        methods = context.get("methods", [])
        if methods:
            prompt += "// Available Methods: {}\n".format(", ".join(methods))
        # Put fields in a comment, single line, separated by commas
        fields = context.get("fields", [])
        if fields:
            prompt += "// Available Fields: {}\n".format(", ".join(fields))
        # Put compositionMembers in a comment, single line, separated by commas
        composition_members = context.get("compositionMembers", [])
        if composition_members:
            prompt += "// Available Composition Members: {}\n".format(", ".join(composition_members))
        # Put inheritedMembers in a comment, single line, separated by commas
        inherited_members = context.get("inheritedMembers", [])
        if inherited_members:
            prompt += "// Available Inherited Members: {}\n".format(", ".join(inherited_members))
        # Put interfaces in a comment, single line, separated by commas
        interfaces = context.get("interfaces", [])
        if interfaces:
            prompt += "// Available Interfaces: {}\n".format(", ".join(interfaces))

        return prompt
        
    def predict_completion(self, code, context):
        prompt = self.create_prompt(context)
        full_code = prompt + code

        inputs = self.tokenizer(full_code, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=32,
            pad_token_id=self.tokenizer.eos_token_id, use_cache=True, do_sample=True, temperature=0.8, top_k=50, top_p=0.95
        )
        outputs = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Remove prompt from output
        if outputs:
            outputs = outputs[len(prompt):].strip()
            outputs = outputs[len(code):].strip()  # Remove the original code part

        # return outputs
        return outputs if outputs else ""
