import json
import argparse
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm
import shutil
import subprocess
from subprocess import TimeoutExpired
import os
from distutils.dir_util import copy_tree

class CompileError(Exception):
    def __init__(self, message):
        super().__init__(message)

class TestError(Exception):
    def __init__(self, message):
        super().__init__(message)

def main():
    bugs_path = args.b
    patches_path = args.p
    number_of_threads = int(args.t)

    with open(bugs_path, 'r') as f:
        bugs = json.load(f)
    with open(patches_path, 'r') as f:
        patches = json.load(f)


    for bug_index, bug_id in enumerate(bugs):
        print(f"Currently on bug {bug_index + 1} out of {len(bugs)}")
        clones_directory, validation_results_path = setup_project(bug_id, patches)
        bug_patches = patches[bug_id]

        with ThreadPoolExecutor(max_workers=number_of_threads) as executor:
            patch_evaluations = []
            for patch_index, patch in enumerate(bug_patches):
                clone_directory = os.path.join(clones_directory, f'patch-{patch_index}')
                patch_evaluation = executor.submit(validate_patch, bugs[bug_id], patch, clone_directory)
                patch_evaluations.append(patch_evaluation)

            print('Evaluating patches...')
            for patch_index, patch_evaluation in tqdm(enumerate(patch_evaluations), total=len(patch_evaluations)):
                try:
                    patch_passes_tests = patch_evaluation.result(timeout=15*60)
                    if patch_passes_tests:
                        write_patch(validation_results_path, bug_patches[patch_index], patch_index, 'plausible')
                    else:
                        write_patch(validation_results_path, bug_patches[patch_index], patch_index, 'failing')
                except CompileError:
                    write_patch(validation_results_path, bug_patches[patch_index], patch_index, 'uncompilable')
                except (TimeoutError, TimeoutExpired):
                    write_patch(validation_results_path, bug_patches[patch_index], patch_index, 'timeout')



def setup_project(bug_id, patches):
    project = bug_id.split('-')[0]
    bug_number = bug_id.split('-')[1]

    tmp_directory = 'tmp'
    original_directory = os.path.join(tmp_directory, 'original_projects', f'{project}-{bug_number}')

    clean_tmp_directory(tmp_directory)
    checkout_defects4j_project(project, bug_number, original_directory)
    clones_directory = create_clones(project, bug_number, patches[bug_id], original_directory)

    validation_results_path = os.path.join('validation_results', bug_id)
    create_patch_directories(validation_results_path)

    return clones_directory, validation_results_path

def clean_tmp_directory(tmp_directory):
    print('Cleaning up tmp directory...')
    if os.path.exists(tmp_directory):
        shutil.rmtree(tmp_directory)

def checkout_defects4j_project(project, bug_number, working_directory):
    command = ["defects4j", "checkout", "-p", project, "-v", f"{bug_number}b", "-w", working_directory]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr)

def create_clones(project, bug_number, patches, original_directory):
    clones_directory = os.path.join('tmp', 'clones', f'{project}-{bug_number}')
    print('Creating project clones...')
    for patch_index, patch in tqdm(enumerate(patches), total=len(patches)):
        os.makedirs(clones_directory, exist_ok=True)
        copy_tree(original_directory, os.path.join(clones_directory, f'patch-{patch_index}'))
    return clones_directory


def create_patch_directories(validation_results_path):
    os.makedirs(os.path.join(validation_results_path, 'uncompilable'), exist_ok=True)
    os.makedirs(os.path.join(validation_results_path, 'failing'), exist_ok=True)
    os.makedirs(os.path.join(validation_results_path, 'plausible'), exist_ok=True)
    os.makedirs(os.path.join(validation_results_path, 'timeout'), exist_ok=True)


def validate_patch(bug, patch, clone_directory):
    apply_patch(bug, patch, clone_directory)
    compile_defects4j_project(clone_directory)
    test_defects4j_project(clone_directory)
    return passes_tests(clone_directory)

def apply_patch(bug, patch, clone_directory):
    project_file = bug['loc']
    start_line = bug['start']
    end_line = bug['end']

    file_path = os.path.join(clone_directory, project_file)
    with open(file_path, 'r', encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = lines[:start_line - 1] + patch.splitlines(keepends=True) + lines[end_line:]

    with open(file_path, 'w', encoding="utf-8") as f:
        f.writelines(new_lines)

def compile_defects4j_project(clone_directory):
    command = ["defects4j", "compile", '-w', clone_directory]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10*60)
    if result.returncode != 0:
        raise CompileError(result.stderr)

def test_defects4j_project(clone_directory):
    command = ["defects4j", "test", '-w', clone_directory]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10*60)
    if result.returncode != 0:
        raise TestError(result.stderr)

def passes_tests(clone_directory):
    with open(os.path.join(clone_directory, 'failing_tests'), 'r') as f:
        return f.read() == ""

def write_patch(validation_results_path, patch, patch_index, result):
    path = os.path.join(validation_results_path, result, f'patch-{patch_index:03d}')
    with open(path, 'w') as f:
       f.write(patch)

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', type=str, required=True, help='bug dataset path')
    parser.add_argument('-p', type=str, required=True, help='patches path')
    parser.add_argument('-t', type=str, required=True, help='number of threads')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_arguments()
    main()