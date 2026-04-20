import yaml
import os
# Author: Reid Roberts
# References: This code was refactored, partuially generated, and modified using tools such as Google's Gemini

# YAML Loader 
    # function that automatically takes the two YAML files as input from the Task-1
def load_yaml_files(file1_path, file2_path):
    
    class DuplicateKeyLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            value = loader.construct_object(value_node)
            
            # If the key already exists, append a unique suffix
            if key in mapping:
                suffix = 1
                new_key = f"{key}_{suffix}"
                while new_key in mapping:
                    suffix += 1
                    new_key = f"{key}_{suffix}"
                mapping[new_key] = value
            else:
                mapping[key] = value
        return mapping

    DuplicateKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping
    )

    try:
        with open(file1_path, 'r', encoding='utf-8') as f1:
            data1 = yaml.load(f1, Loader=DuplicateKeyLoader)
        with open(file2_path, 'r', encoding='utf-8') as f2:
            data2 = yaml.load(f2, Loader=DuplicateKeyLoader)
        return data1, data2
    except FileNotFoundError as e:
        print(f"Error loading files: {e}")
        return None, None


# KDE Extraction based on expected Dict order
def extract_kdes(yaml_data):
    
    kdes = {}
    if not yaml_data:
        return kdes
        
    for key, value in yaml_data.items():
        # Look for dictionaries that contain both 'name' and 'requirements'
        if isinstance(value, dict) and 'name' in value and 'requirements' in value:
            name = value['name']
            reqs = value['requirements']
            
            if not isinstance(reqs, list):
                reqs = [reqs]
                
            kdes[name] = reqs
    return kdes


# Name Comparator
    # function that identifies differences in the two YAML files with respect to names of key data elements.
def compare_element_names(data1, file1_name, data2, file2_name, output_txt_path):
    """
    Compares only the names of the Key Data Elements and outputs differences.
    """
    kdes1 = extract_kdes(data1)
    kdes2 = extract_kdes(data2)
    
    names1 = set(kdes1.keys())
    names2 = set(kdes2.keys())
    
    differences = names1.symmetric_difference(names2)
    
    with open(output_txt_path, 'w', encoding='utf-8') as f:
        if not differences:
            f.write('NO DIFFERENCES IN REGARDS TO ELEMENT NAMES\n')
        else:
            for name in differences:
                f.write(f"{name}\n")
                
    print(f"Name comparison complete. Saved to {output_txt_path}")

# Multi Comparator
    # function that identifies differences in the two YAML files with respect to (i) names of key data elements; and (ii) requirements for the key data elements.
def compare_element_requirements(data1, file1_name, data2, file2_name, output_txt_path):
    
    kdes1 = extract_kdes(data1)
    kdes2 = extract_kdes(data2)
    
    differences = []
    
    # Get all unique element names across both files
    all_names = set(kdes1.keys()).union(set(kdes2.keys()))
    
    for name in all_names:
        # Scenario 1: Element is in File 1 but missing in File 2
        if name in kdes1 and name not in kdes2:
            differences.append(f"{name},ABSENT-IN-{file2_name},PRESENT-IN-{file1_name},NA")
            
        # Scenario 2: Element is in File 2 but missing in File 1
        elif name in kdes2 and name not in kdes1:
            differences.append(f"{name},ABSENT-IN-{file1_name},PRESENT-IN-{file2_name},NA")
            
        # Scenario 3: Element exists in both, so we check requirements
        else:
            reqs1 = set(kdes1[name])
            reqs2 = set(kdes2[name])
            
            # Reqs present in File 1 but missing in File 2
            for req in reqs1 - reqs2:
                differences.append(f"{name},ABSENT-IN-{file2_name},PRESENT-IN-{file1_name},{req}")
                
            # Reqs present in File 2 but missing in File 1
            for req in reqs2 - reqs1:
                differences.append(f"{name},ABSENT-IN-{file1_name},PRESENT-IN-{file2_name},{req}")
                
    with open(output_txt_path, 'w', encoding='utf-8') as f:
        if not differences:
            f.write('NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS\n')
        else:
            for diff in differences:
                f.write(f"{diff}\n")
                
    print(f"Requirement comparison complete. Saved to {output_txt_path}")

# main function to be called
def main():
    
    #testing
    file1_path = input("Enter path for the first YAML file (e.g., cis-r1.yaml): ").strip()
    file2_path = input("Enter path for the second YAML file (e.g., cis-r2.yaml): ").strip()
    
    file1_name = os.path.basename(file1_path)
    file2_name = os.path.basename(file2_path)
    
    # 1. Load Files
    print("\nLoading files...")
    data1, data2 = load_yaml_files(file1_path, file2_path)
    
    if data1 is None or data2 is None:
        print("Failed to load one or both YAML files. Exiting.")
        return

    # Create output directory if it doesn't exist
    output_dir = "OutputTXT"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 2. Compare Names
    names_output = os.path.join(output_dir, f"names_diff_{file1_name}_vs_{file2_name}.txt")
    compare_element_names(data1, file1_name, data2, file2_name, names_output)
    
    # 3. Compare Requirements
    reqs_output = os.path.join(output_dir, f"reqs_diff_{file1_name}_vs_{file2_name}.txt")
    compare_element_requirements(data1, file1_name, data2, file2_name, reqs_output)

    print("\nTask 2 Execution Finished Successfully.")

if __name__ == '__main__':
    main()