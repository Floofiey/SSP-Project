import os
from Comparator import load_yaml_files, compare_element_names, compare_element_requirements

def run_test_cases():
    f1 = os.path.dirname(os.path.realpath(__file__)) + '/OutputYAMLs/cis-r1.yaml'
    f2 = os.path.dirname(os.path.realpath(__file__)) + '/OutputYAMLs/cis-r3.yaml'
    
    print("--- Running Test Cases ---")

    # 1. Test: load_yaml_files
    # Validates that the YAMLs are parsed into Python dictionaries
    data1, data2 = load_yaml_files(f1, f2)
    if data1 and data2:
        print(f"\n---------------------------------------------------------\n[PASS] load_yaml_files: Successfully loaded {f1} and {f2}")
    else:
        print("\n---------------------------------------------------------\n[FAIL] load_yaml_files: Failed to load files")

    # 2. Test: compare_element_names
    name_output = "test_names_diff.txt"
    compare_element_names(data1, f1, data2, f2, name_output)
    
    if os.path.exists(name_output):
        with open(name_output, 'r') as f:
            content = f.read()
            print(f"\n---------------------------------------------------------\n[PASS] compare_element_names: Output generated.\n\nDifferences found:\n{content.strip()}")
    
    # 3. Test: compare_element_requirements
    req_output = "test_reqs_diff.txt"
    compare_element_requirements(data1, f1, data2, f2, req_output)
    
    if os.path.exists(req_output):
        with open(req_output, 'r') as f:
            content = f.read()
            print(f"\n---------------------------------------------------------\n[PASS] compare_element_requirements: Output generated.\n\nDifferences found:\n{content.strip()}")

if __name__ == "__main__":
    run_test_cases()