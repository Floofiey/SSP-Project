from transformers import AutoTokenizer, BitsAndBytesConfig, Gemma3ForCausalLM
import torch
import pypdf
import math
import yaml
import ast

model_id = "google/gemma-3-1b-it"

quantization_config = BitsAndBytesConfig(load_in_8bit=True)

model = Gemma3ForCausalLM.from_pretrained(
    model_id, quantization_config=quantization_config
).eval()

tokenizer = AutoTokenizer.from_pretrained(model_id)
f = pypdf.PdfReader('SourcePDFs/cis-r3.pdf')
pdfstring = ""
pagenum = math.floor(len(f.pages) / 4)
for i in range(pagenum):
    page = f.pages[i]
    tempstring = page.extract_text()
    pdfstring += " " + tempstring
example = """
element3:
  name: Kubelet Security Configuration
  requirements:
    req1: "3.2.1 (Automated, L1) Anonymous authentication must be disabled — set
           authentication.anonymous.enabled: false in the kubelet config file or pass
           --anonymous-auth=false as a command-line argument."
    req2: "3.2.2 (Automated, L1) --authorization-mode must not be set to AlwaysAllow —
           verify the argument is absent or set to a restrictive mode (e.g., Webhook)."
    req3: "3.2.3 (Automated, L1) A Client CA File must be configured — ensure
           --client-ca-file is set to a valid CA bundle in the kubelet config."
    req4: "3.2.4 (Automated, L1) --read-only-port must be disabled (set to 0) to prevent
           unauthenticated access to kubelet metrics."
    req5: "3.2.5 (Automated, L1) --streaming-connection-idle-timeout must not be 0 —
           a non-zero timeout prevents indefinitely open streaming connections."
    req6: "3.2.6 (Automated, L1) --make-iptables-util-chains must be set to true to ensure
           kubelet manages iptable rules correctly."
    req7: "3.2.7 (Automated, L1) --eventRecordQPS must be set to 0 or an appropriate
           positive value that ensures adequate event capture without overloading the API server."
    req8: "3.2.8 (Automated, L1) --rotate-certificates must not be present or must be set
           to true to enable automatic client certificate rotation."
    req9: "3.2.9 (Automated, L1) RotateKubeletServerCertificate must be set to true in the
           feature gates to enable automatic server certificate rotation."""
messages = [
    [
        {
            "role": "system",
            "content": [{"type": "text", "text": "You are a CIS requirement writer seeking to organize past documents in a more easily storable manner."},]
        },
        {
            "role": "user",
            "content": [{"type": "text", "text": "Take the given text and identify key data elements within it. You should only return a nested dictionary written as a Python code block focusing on the found key data elements and all of the specific requirements tied to them by following the format of this example:" + example + "\nDo not give an overview of the document. Do not simply summarize the sections or pages. Do not organize by page. Do not list recommendations nor remediations. Explicitly focus on the data element names and the requirements tied to them, citing the requirement number for each entry. Again, format it as a Python nested dictionary within a code block. Here is the text to analyze: " + pdfstring}, ]
        },
    ],
]

inputs = tokenizer.apply_chat_template(
    messages,
    add_generation_prompt=True,
    tokenize=True,
    return_dict=False,
    return_tensors="pt",
).to(model.device)

with torch.inference_mode():
    outputs = model.generate(inputs, max_new_tokens= 100000)

outfile = open('testoutput.txt', 'w')
testyaml = open('testyaml.yaml', 'w')
outputs = tokenizer.decode(outputs, skip_special_tokens = False)
totalstring = ''
for string in outputs:
    totalstring += string
totalstring = totalstring.split('<end_of_turn>')[1]

for string in outputs:
    outfile.write(string)

yamlstring = totalstring.split("```")[1]
yamlstring = yamlstring.replace("python", "")
yamlstring = yamlstring.replace('\n', "")
yamlstring = yamlstring.replace('\t', " ")
outfile.write(yamlstring)
yamlstring = eval(yamlstring)

yaml.dump(yamlstring, testyaml)