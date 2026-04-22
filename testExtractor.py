import os
import Extractor
import pypdf
from transformers import AutoTokenizer, BitsAndBytesConfig, Gemma3ForCausalLM
import torch

sourcePath = os.path.dirname(os.path.realpath(__file__)) + "/SourcePDFs/"
pdfoutPath = os.path.dirname(os.path.realpath(__file__)) + "/OutputPDFs/"

def testPdfSplit():
    sourcestring = sourcePath + "cis-r1.pdf"
    pdf = pypdf.PdfReader(sourcestring)
    splits = Extractor.calcSplits(len(pdf.pages))
    Extractor.PDFsplit(sourcestring, "1", splits)
    try:
        outstring = pdfoutPath + "cis-r11.pdf"
        fin = open(outstring, 'x')
        print("ERROR: Pdf split test failed")
    except: 
        print ("Pdf successfully split.")


guide = """
element1:
    name: Kubelet Security Configuration
    requirements:
        req1: "3.2.1 (Automated, L1) Anonymous authentication must be disabled - set
            authentication.anonymous.enabled: false in the kubelet config file or pass
            --anonymous-auth=false as a command-line argument."
        req2: "3.2.2 (Automated, L1) --authorization-mode must not be set to AlwaysAllow -
            verify the argument is absent or set to a restrictive mode (e.g., Webhook)."
        req3: "3.2.3 (Automated, L1) A Client CA File must be configured - ensure
            --client-ca-file is set to a valid CA bundle in the kubelet config."
        req4: "3.2.4 (Automated, L1) --read-only-port must be disabled (set to 0) to prevent
            unauthenticated access to kubelet metrics."
        req5: "3.2.5 (Automated, L1) --streaming-connection-idle-timeout must not be 0 -
                a non-zero timeout prevents indefinitely open streaming connections."
        req6: "3.2.6 (Automated, L1) --make-iptables-util-chains must be set to true to ensure
                kubelet manages iptable rules correctly."
        req7: "3.2.7 (Automated, L1) --eventRecordQPS must be set to 0 or an appropriate
                positive value that ensures adequate event capture without overloading the API server."
        req8: "3.2.8 (Automated, L1) --rotate-certificates must not be present or must be set
                to true to enable automatic client certificate rotation."
        req9: "3.2.9 (Automated, L1) RotateKubeletServerCertificate must be set to true in the
                feature gates to enable automatic server certificate rotation.
element2:
    name: CNI Plugin and Network Policies
        requirements:
            req1: "4.3.1 (Manual, L1) The CNI plugin must support network policies - confirm the
            deployed CNI (e.g., Calico, Cilium, or VPC CNI with network policy support)
            enforces NetworkPolicy resources."
            req2: "4.3.2 (Automated, L1) All Namespaces must have Network Policies defined -
            create default-deny ingress/egress NetworkPolicy objects in every namespace."
element3:
    name: Secrets Management
    requirements:
        req1: "4.4.1 (Automated, L1) Secrets must be mounted as files rather than exposed as
            environment variables - use volume mounts with secretKeyRef, not env.valueFrom."
        req2: "4.4.2 (Manual, L2) Consider using an external secret store (e.g., AWS Secrets Manager,
            HashiCorp Vault) instead of native Kubernetes Secrets for enhanced protection."
element4:
    name: General Namespace Policies
    requirements:
        req1: "4.5.1 (Manual, L1) Administrative boundaries must be created between resources
            using namespaces - group workloads by team, environment, or sensitivity level."
        req2: "4.5.2 (Automated, L2) The default namespace must not be used for workload
            deployment - all application resources must reside in explicitly named namespaces."
"""

def test_prompters():
    zero = Extractor.zeroShotPrompter(1, 1)
    assert zero, "ERROR: Zero Shot Prompt Failed to initialize"
    few = Extractor.fewShotPrompter(1, 1)
    assert few, "ERROR: Few Shot Prompt Failed to initialize"
    chain = Extractor.thoughtChainPrompter(1, 1, guide)
    assert chain, "ERROR: Chain of Thought Prompt Failed to initialize"
    print("All prompt generators tested, If there's no errors above, you're good.")

def testgeneration():
    model_id = "google/gemma-3-1b-it"
    quantization_config = BitsAndBytesConfig(load_in_8bit=True, device = 'auto')
    model = Gemma3ForCausalLM.from_pretrained(
        model_id, quantization_config=quantization_config
    ).eval()
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    prompt = Extractor.zeroShotPrompter(1, 1)
    zeroPrompt = [
            [
                {
                    "role":"system",
                    "content":[{"type": "text", "text": "You are an analyst designed to ensure compliance with best practices in data security."},]
                },
                {
                    "role":"user",
                    "content":[{"type": "text", "text" : prompt}, ]
                },
            ],
        ]
    inputs = tokenizer.apply_chat_template(
            zeroPrompt,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=False,
            return_tensors="pt",
        ).to(model.device)
    with torch.inference_mode():
        outputs = model.generate(inputs, max_new_tokens=1000)
    outputs = tokenizer.batch_decode(outputs)
    assert outputs, "ERROR: Zero Shot Generation failed"

    
    prompt = Extractor.fewShotPrompter(1, 1)
    zeroPrompt = [
            [
                {
                    "role":"system",
                    "content":[{"type": "text", "text": "You are an analyst designed to ensure compliance with best practices in data security."},]
                },
                {
                    "role":"user",
                    "content":[{"type": "text", "text" : prompt}, ]
                },
            ],
        ]
    inputs = tokenizer.apply_chat_template(
            zeroPrompt,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=False,
            return_tensors="pt",
        ).to(model.device)
    with torch.inference_mode():
        outputs = model.generate(inputs, max_new_tokens=3000)
    outputs = tokenizer.batch_decode(outputs)
    assert outputs, "ERROR: Few Shot Generation failed"


    
    prompt = Extractor.thoughtChainPrompter(1, 1, guide)
    zeroPrompt = [
            [
                {
                    "role":"system",
                    "content":[{"type": "text", "text": "You are an analyst designed to ensure compliance with best practices in data security."},]
                },
                {
                    "role":"user",
                    "content":[{"type": "text", "text" : prompt}, ]
                },
            ],
        ]
    inputs = tokenizer.apply_chat_template(
            zeroPrompt,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=False,
            return_tensors="pt",
        ).to(model.device)
    with torch.inference_mode():
        outputs = model.generate(inputs, max_new_tokens=10000)
    outputs = tokenizer.batch_decode(outputs)
    assert outputs, "ERROR: Chain of Thought Generation failed"

    print("All Generation tests complete! If no errors above, you're good.")

def runeverything():
    testPdfSplit()
    test_prompters()
    testgeneration()