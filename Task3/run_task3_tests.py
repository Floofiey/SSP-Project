from Task3.kubescape_pipeline import *


def run_task3():
    test_detect_differences()
    test_map_to_kubescape_controls()
    test_run_kubescape_scan()
    test_export_to_csv()

    print("Done!")