import sys
from Task3.kubescape_pipeline import main as task3
from Extractor import extractor as task1
from Comparator import task2

args = sys.argv


print("Arguments are ", args)

if len(args) != 3:
    raise ValueError("There should be exactly two arguments in addition to the file name")

input1_file_name = args[1]
input2_file_name = args[2]


yaml1_path, yaml2_path = task1(input1_file_name, input2_file_name)

names_out, req_out = task2(yaml1_path, yaml2_path)

task3(names_out, req_out, "Task3/project-yamls.zip")