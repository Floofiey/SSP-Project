from transformers import AutoTokenizer, BitsAndBytesConfig, Gemma3ForCausalLM
import torch
import pypdf
import math
import yaml
import os


#Okay so this code is just copied from Hugging Face's tutorial
model_id = "google/gemma-3-1b-it"

quantization_config = BitsAndBytesConfig(load_in_8bit=True, device = 'auto')

model = Gemma3ForCausalLM.from_pretrained(
    model_id, quantization_config=quantization_config
).eval()

tokenizer = AutoTokenizer.from_pretrained(model_id)

#Getting a string for the directory for file ops
dir_path = os.path.dirname(os.path.realpath(__file__))

#This function copied directly from G4G, Source: https://www.geeksforgeeks.org/python/working-with-pdf-files-in-python/
def PDFsplit(pdf, splits):
    reader = pypdf.PdfReader(pdf)

    # starting index of first slice
    start = 0

    # starting index of last slice
    end = splits[0]


    for i in range(len(splits)+1):
        # creating pdf writer object for (i+1)th split
        writer = pypdf.PdfWriter()

        # output pdf file name
        outputpdf = "OutputPDFS\\" + pdf.split('.pdf')[0] + str(i) + '.pdf'

        # adding pages to pdf writer object
        for page in range(start,end):
            writer.add_page(reader.pages[page])

            # writing split pdf pages to pdf file
            with open(outputpdf, "wb") as f:
                writer.write(f)

        # interchanging page split start position for next split
        start = end
        try:
            # setting split end position for next split
            end = splits[i+1]
        except IndexError:
            # setting split end position for last split
            end = len(reader.pages)

    #SHOULDN'T BE NECESSARY, BUT HERE IN CASE
    #UPDATE: NECESSARY.
def calcSplits(totalpages):
    #This should return the splits we need to parse the PDF's properly
    half = math.floor(totalpages / 2)
    quarter = math.floor(half / 2)
    three_fourths = math.floor(half + quarter)
    finArray = [quarter, half, three_fourths]
    return finArray

def zeroShotPrompter(filenum, splitnum):
    #okay let's fuck around and find out
    splitname = dir_path + 'OutputPDFs/cis-r' + str(filenum) + str(splitnum) + '.pdf'
    splitfile = pypdf.PdfReader(splitname)
    finString = 'Take the following piece of a requirements document, and identify key data elements as well as all requirements the data element is mapped to, returning a Python nested dictionary of elements and requirements:  '
    for page in splitfile.pages:
        finString += page.extract_text()
    splitfile.close()
    return finString

def fewShotPrompter(filenum, splitnum):
    #AS WITH EVERYTHING IN THIS FILE, LET'S COPY/PASTE SOMETHING ELSE
    splitname = dir_path + 'OutputPDFs/cis-r' + str(filenum) + str(splitnum) + '.pdf'
    splitfile = pypdf.PdfReader(splitname)
    finString = "Take the following piece of a requirements document, and identify key data elements as well as all ' \
                   requirements the data element is mapped to, returning a Python nested dictionary of elements and requirements with the format {elementnumber : [{name : }, {requirements : [req1, req2, ...]}]}:  "
    for page in splitfile.pages:
        finString += page.extract_text()
    splitfile.close()
    return finString

def thoughtChainPrompter(filenum, splitnum, example):
    splitname = dir_path + 'OutputPDFs/cis-r' + str(filenum) + str(splitnum) + '.pdf'
    splitfile = pypdf.PdfReader(splitname)
    finString = "Take the given text and identify key data elements within it. You should only return a nested dictionary written as a Python code block focusing on the found key data elements and all of the specific requirements tied to them by following the format of this example:" + example + "\nDo not give an overview of the document. Do not simply summarize the sections or pages. Do not organize by page. Do not list recommendations nor remediations. Explicitly focus on the data element names and the requirements tied to them, citing the requirement number for each entry. Again, format it as a Python nested dictionary within a code block. Here is the text to analyze: "
    for page in splitfile.pages:
        finString += page.extract_text()
    splitfile.close()
    return finString

def extractor():
    print("Please input the number of the first CIS Requirement document you wish to run analysis on: ")
    input1 = input()
    while not input1.isnumeric() or 0 > int(input1) or int(input1) > 4:
        print("Invalid input. Again, please input the first CIS document number (1-4) that you wish to analyze: ")
        input1 = input()
    print("Thank you. Please input the number of the second CIS Requirement document you wish to run analysis on: ")
    input2 = input()
    while not input2.isnumeric() or 0 > int(input2) or int(input2) > 4:
        print("Invalid input. Again, please input the second CIS document number (1-4) that you wish to analyze: ")
        input2 = input()
    print("Thank you.")

    #Build the file names and initialize the pdfs
    fileString1 = dir_path + "SourcePDFs/cis-r" + str(input1) + ".pdf"
    fileString2 = "SourcePDFs/cis-r" + str(input2) + ".pdf"
    file1 = pypdf.PdfReader(fileString1)


    #Build the splits for dividing the files (Dividing each of them into 4,
       #This will likely make this take a lot longer, but will ensure that it 
        #can parse each file)
        #DON'T THINK I NEED, KEEPING IN CASE I DO.
        #UPDATE: NEEDED.
    splits1 = calcSplits(len(file1.pages))
    

    #After these calls, there should be 4 files for each document,
    #    labelled "cis-r[x][splitnumber].pdf
    PDFsplit(fileString1, splits1)
    
    file1.close()
#Alright let's run these 0-shot prompts.
   
        #Step 1: I'm making the output file.
    outstring = dir_path + "OutputTXT/cis-r" + str(input1)
    outfile1 = open(outstring + ".txt", 'w')
    outfile1.write("Gemma3-1B \nPrompt: Take the following piece of a requirements document, and identify key data elements as well as all requirements the data' \
                        element is mapped to, returning a Python nested dictionary of elements and requirements: \nZero shot  \n output: ")
    for i in range(4):
        currPrompt = ''
        currPrompt = zeroShotPrompter(input1, i)
        #Okay this should rewrite the prompt every time to feed it into this nightmare
        #   And turn it into something usable
        zeroPrompt1 = [
            [
                {
                    "role":"system",
                    "content":[{"type": "text", "text": "You are an analyst designed to ensure compliance with best practices in data security."},]
                },
                {
                    "role":"user",
                    "content":[{"type": "text", "text" : currPrompt}, ]
                },
            ],
        ]
        #This is what the LLM actually sees.\
        inputs = tokenizer.apply_chat_template(
            zeroPrompt1,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=False,
            return_tensors="pt",
        ).to(model.device)
        
        #This generates the response
        with torch.inference_mode():
            outputs = model.generate(inputs, max_new_tokens=1000)
        outputs = tokenizer.batch_decode(outputs)
        
        #I'm gonna do something shady here and write the entire thing to a single string
        #So I can break it up by turn to isolate just the response.
        totalstring = ''
        for string in outputs:
            totalstring += string
        totalstring = totalstring.split('<end_of_turn>')[1]
        outfile1.write(totalstring)

    

#BEGIN FEW SHOT STUFF HERE
    outfile1.write("\n \nGemma3-1B \nPrompt: Take the following piece of a requirements document, and identify key data elements as well as all requirements the data element is mapped to, returning a Python nested dictionary of elements and requirements with the format {elementnumber : [{name : }, {requirements : [req1, req2, ...]}]}: \nFew shot  \n output: ")
    for i in range(4):
        currPrompt = ''
        currPrompt = fewShotPrompter(input1, i)
        #Okay this should rewrite the prompt every time to feed it into this nightmare
        #   And turn it into something usable
        fewPrompt1 = [
            [
                {
                    "role":"system",
                    "content":[{"type": "text", "text": "You are an analyst designed to ensure compliance with best practices in data security."},]
                },
                {
                    "role":"user",
                    "content":[{"type": "text", "text" : currPrompt}, ]
                },
            ],
        ]
        #This is what the LLM actually sees.\
        inputs = tokenizer.apply_chat_template(
            fewPrompt1,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=False,
            return_tensors="pt",
        ).to(model.device)
        
        #This generates the response
        with torch.inference_mode():
            outputs = model.generate(inputs, max_new_tokens=3000)
        outputs = tokenizer.batch_decode(outputs)
        
        #I'm gonna do something shady here and write the entire thing to a single string
        #So I can break it up by turn to isolate just the response.
        totalstring = ''
        for string in outputs:
            totalstring += string
        totalstring = totalstring.split('<end_of_turn>')[1]
        outfile1.write(totalstring)

    
#BEGIN CHAIN OF THOUGHT
    #okay I need something to actually direct this thing.
    guide = """
    element1:
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
    
    #WATCH THIS DRIVE, NOW WITH YAML
    outyaml1 = open(dir_path + "OutputYAMLs/" + fileString1.split('.pdf')[0] + '.yaml', 'w')
    outfile1.write("\n \nGemma3-1B \nPrompt: \"Take the given text and identify key data elements within it. You should only return a nested dictionary written " \
        "as a Python code block focusing on the found key data elements and all of the specific requirements tied to them by following the format of this example:" + guide + 
        "\nDo not give an overview of the document. Do not simply summarize the sections or pages. Do not organize by page. Do not list recommendations nor remediations. Explicitly "
        "focus on the data element names and the requirements tied to them, citing the requirement number for each entry. Again, format it as a Python nested dictionary within a "
        "code block. Here is the text to analyze:  \nChain of Thought  \n output: ")
    for i in range(4):
        #Worst update I've done so far:
        #I'm going to make this loop until it gets a valid input.
        #No more gambling! But oh my god this thing is gonna run for four hours.
        valid = False
        attempts = 0
        while not valid:
            attempts += 1
            if attempts > 5:
                print ("Part " + str(i + 1) + " of pdf 1 is being deemed impossible due to repeated failures of valid output. Continuing to next string.")
                break
            currPrompt = ''
            currPrompt = thoughtChainPrompter(input1, i, guide)
            #Okay this should rewrite the prompt every time to feed it into this nightmare
            #   And turn it into something usable
            fewPrompt1 = [
                [
                    {
                        "role":"system",
                        "content":[{"type": "text", "text": "You are a CIS requirement writer seeking to organize past documents in a more easily storable manner."},]
                    },
                    {
                        "role":"user",
                        "content":[{"type": "text", "text" : currPrompt}, ]
                    },
                ],
            ]
            #This is what the LLM actually sees.\
            inputs = tokenizer.apply_chat_template(
                fewPrompt1,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=False,
                return_tensors="pt",
            ).to(model.device)
        
            #This generates the response
            with torch.inference_mode():
                outputs = model.generate(inputs, max_new_tokens=5000)
            outputs = tokenizer.batch_decode(outputs)
        
            #I'm gonna do something shady here and write the entire thing to a single string
            #So I can break it up by turn to isolate just the response.
            totalstring = ''
            for string in outputs:
                totalstring += string
            totalstring = totalstring.split('<end_of_turn>')[1]
        
            #OKAY SO. In order to get this to parse properly to work in YAML
            #I had to cut down the response to JUST the dictionary, hence the split.
            #The replacements are to make it actually convertible to code
            #Because APPARENTLY python doesn't like random amounts of indents and newlines.
            if len(totalstring.split("```")) < 2:
                yamlstring = totalstring.split("```")[0]
            else:
                yamlstring = totalstring.split("```")[1]
            yamlstring = yamlstring.replace("python", "")
            yamlstring = yamlstring.replace('\n', "")
            yamlstring = yamlstring.replace('\t', "")

            try:
                yamlstring = eval(yamlstring)
                yaml.dump(yamlstring, outyaml1)
                valid = True
                print("Part " + str (i + 1) + " of PDF 1 successfully analyzed, continuing.")
            except:
                print ("welp, couldn't write part " + str(i + 1) + " of the yaml file, retrying.")
            if valid:
                outfile1.write(totalstring)
        

    outyaml1.close()
    outfile1.close()
    
#Baller, let's do file 2
    
    file2 = pypdf.PdfReader(fileString2)
    splits2 = calcSplits(len(file2.pages))
    PDFsplit(fileString2, splits2)
    file2.close()

    #Yo watch this copy/paste from file1
    outstring = dir_path + "OutputTXT/cis-r" + str(input2) + "(2).txt"
    outfile2 = open(outstring, 'w')
    outfile2.write("Gemma3-1B \nPrompt: Take the following piece of a requirements document, and identify key data elements as well as all requirements the data' \
                        element is mapped to, returning a Python nested dictionary of elements and requirements: \nZero shot  \n output: ")
    for i in range(4):
        currPrompt = ''
        currPrompt = zeroShotPrompter(input2, i)
        #Okay this should rewrite the prompt every time to feed it into this nightmare
        #   And turn it into something usable
        zeroPrompt2 = [
            [
                {
                    "role":"system",
                    "content":[{"type": "text", "text": "You are an analyst designed to ensure compliance with best practices in data security."},]
                },
                {
                    "role":"user",
                    "content":[{"type": "text", "text" : currPrompt}, ]
                },
            ],
        ]
        #This is what the LLM actually sees.\
        inputs = tokenizer.apply_chat_template(
            zeroPrompt2,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=False,
            return_tensors="pt",
        ).to(model.device)
        
        #This generates the response
        with torch.inference_mode():
            outputs = model.generate(inputs, max_new_tokens=1000)
        outputs = tokenizer.batch_decode(outputs)
        
        #Same as before, cutting it to isolate output.
        totalstring = ''
        for string in outputs:
            totalstring += string
        totalstring = totalstring.split('<end_of_turn>')[1]
        outfile2.write(totalstring)
    
    #Aaaaaand that's file 2 for zero prompt!
    #But hear me out: what if we basically copy/paste it AGAIN for the other two prompt styles?
    #And just change the function names to few shot/thought_chain?

    outfile2.write("\n\nGemma3-1B \nPrompt: Take the following piece of a requirements document, and identify key data elements as well as all requirements the data element is mapped to, returning a Python nested dictionary of elements and requirements with the format {elementnumber : [{name : }, {requirements : [req1, req2, ...]}]}: \nFew shot  \n output: ")
    for i in range(4):
        currPrompt = ''
        currPrompt = fewShotPrompter(input2, i)
        #Okay this should rewrite the prompt every time to feed it into this nightmare
        #   And turn it into something usable
        fewPrompt2 = [
            [
                {
                    "role":"system",
                    "content":[{"type": "text", "text": "You are an analyst designed to ensure compliance with best practices in data security."},]
                },
                {
                    "role":"user",
                    "content":[{"type": "text", "text" : currPrompt}, ]
                },
            ],
        ]
        #This is what the LLM actually sees.\
        inputs = tokenizer.apply_chat_template(
            fewPrompt2,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=False,
            return_tensors="pt",
        ).to(model.device)
        
        #This generates the response
        with torch.inference_mode():
            outputs = model.generate(inputs, max_new_tokens=2000)
        outputs = tokenizer.batch_decode(outputs)
        
        #Same as before, cutting it to isolate output.
        totalstring = ''
        for string in outputs:
            totalstring += string
        totalstring = totalstring.split('<end_of_turn>')[1]
        outfile2.write(totalstring)
    
    #Aaaaaand that's file 2 for few prompt!
    #More unabashed copying inbound!
    outyaml2 = open(dir_path + "OutputYAMLs/" + fileString2.split('.pdf')[0] + '.yaml', 'w')
    outfile2.write("\n \nGemma3-1B \nPrompt: Take the given text, a piece of a CIS benchmark document, and identify key data elements within it. You should only return " \
        "a nested dictionary formatted for Python focusing on the found key data elements and all of the specific requirements tied to them by following the format of this " \
        "example:" + guide + "\nDo not give an overview of the document. Do not simply summarize the sections or pages. Do not organize by page. Do not list recommendations "
        "nor remediations. Explicitly focus on the data element names and the requirements tied to them, citing the requirement number for each entry. Here is the text to analyze: \nChain of Thought  \n output: ")
    for i in range(4):
        valid = False
        attempts = 0
        while not valid:
            attempts += 1
            #Lets the function time out, essentially.
            if attempts >= 5:
                print("Part " + str(i + 1) + " of pdf 2 is being deemed impossible due to repeated failures of valid output. Continuing to next string.")
                break
            currPrompt = ''
            currPrompt = thoughtChainPrompter(input2, i, guide)
            #Okay this should rewrite the prompt every time to feed it into this nightmare
            #   And turn it into something usable
            thoughtChainPrompt2 = [
                [
                    {
                        "role":"system",
                        "content":[{"type": "text", "text": "You are a CIS requirement writer seeking to organize past documents in a more easily storable manner."},]
                    },
                    {
                        "role":"user",
                        "content":[{"type": "text", "text" : currPrompt}, ]
                    },
                ],
            ]
            #This is what the LLM actually sees.\
            inputs = tokenizer.apply_chat_template(
                thoughtChainPrompt2,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=False,
                return_tensors="pt",
            ).to(model.device)
        
            #This generates the response
            with torch.inference_mode():
                outputs = model.generate(inputs, max_new_tokens=5000)
            outputs = tokenizer.batch_decode(outputs)
        
            #I'm gonna do something shady here and write the entire thing to a single string
            #So I can break it up by turn to isolate just the response.
            totalstring = ''
            for string in outputs:
                totalstring += string
            totalstring = totalstring.split('<end_of_turn>')[1]
        
            #OKAY SO. In order to get this to parse properly to work in YAML
            #I had to cut down the response to JUST the dictionary, hence the split.
            #The replacements are to make it actually convertible to code
            #Because APPARENTLY python doesn't like random amounts of indents and newlines.
            if len(totalstring.split("```")) < 2:
                yamlstring = totalstring.split("```")[0]
            else:
                yamlstring = totalstring.split("```")[1]
            yamlstring = yamlstring.replace("python", "")
            yamlstring = yamlstring.replace('\n', "")
            yamlstring = yamlstring.replace('\t', "")

            try:
                yamlstring = eval(yamlstring)
                yaml.dump(yamlstring, outyaml1)
                valid = True
                print("Part " + str(i + 1) + " of PDF 2 successfully analyzed, continuing.")
            except:
                print ("welp, couldn't write part " + str(i + 1) + " of yaml file 2, retrying.")
            if valid:
                outfile2.write(totalstring)

        
    outfile2.close()
    outyaml2.close()

if __name__ == '__main__':
    extractor()