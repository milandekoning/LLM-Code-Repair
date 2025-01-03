import json
import argparse
import os
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from distutils.dir_util import copy_tree

from tqdm import tqdm

def timeout_handler(signum, frame):
    raise TimeoutError("Function execution exceeded the timeout limit")

class Validator:

    def __init__(self, bug_id, bug_entry, all_patches,validation_results_path, working_directory):
        self.bug_id = bug_id
        self.project = bug_id.split('-')[0]
        self.bug_number = bug_id.split('-')[1]
        self.bug = bug_entry
        self.validation_results_path = validation_results_path
        self.working_directory = working_directory
        self.all_patches = all_patches

    def validate_patches(self, patch_indices):
        for patch_index in patch_indices:
            self.validate_patch(patch_index)

    def validate_patch(self, patch_index):
        self.apply_patch(patch_index)
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.compile_defects4j_project, patch_index)
                future.result(timeout=15 * 60)
        except TimeoutError:
            self.write_patch(patch_index, 'timeout')
        except Exception as e:
            self.write_patch(patch_index, 'uncompilable')
            return

        self.test_defects4j_project(patch_index)
        failing_tests_output = self.get_failing_tests_output(patch_index)

        if failing_tests_output == "":
            self.write_patch(patch_index, 'plausible')
        else:
            self.write_patch(patch_index, 'failing')



    def apply_patch(self, patch_index):
        project_file = self.bug['loc']
        start_line = self.bug['start']
        end_line = self.bug['end']
        patch = self.all_patches[patch_index]

        file_path = os.path.join(self.working_directory, f'patch-{patch_index}', project_file)
        with open(file_path, 'r', encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = lines[:start_line - 1] + patch.splitlines(keepends=True) + lines[end_line:]

        with open(file_path, 'w', encoding="utf-8") as f:
            f.writelines(new_lines)

    def compile_defects4j_project(self, patch_index):
        patch_directory = os.path.join(self.working_directory, f'patch-{patch_index}')
        command = ["defects4j", "compile", '-w', patch_directory]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr)

    def test_defects4j_project(self, patch_index):
        patch_directory = os.path.join(self.working_directory, f'patch-{patch_index}')
        command = ["defects4j", "test", '-w', patch_directory]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr)

    def get_failing_tests_output(self, patch_index):
        with open(os.path.join(self.working_directory, f'patch-{patch_index}', 'failing_tests'), 'r') as f:
            return f.read()

    def write_patch(self, patch_index, result):

        path = os.path.join(self.validation_results_path, result,f'patch-{patch_index}')
        with open(path, 'w') as f:
           f.write(self.all_patches[patch_index])


def checkout_defects4j_project(project, bug_number, working_directory):
    command = ["defects4j", "checkout", "-p", project, "-v", f"{bug_number}b", "-w", working_directory]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr)

def main():
    bugs_path = args.b
    patches_path = args.p

    number_of_threads = int(args.t)

    with open(bugs_path, 'r') as f:
        bugs = json.load(f)

    with open(patches_path, 'r') as f:
        patches = json.load(f)


    for bug_id in tqdm(bugs):
        project = bug_id.split('-')[0]
        bug_number = bug_id.split('-')[1]
        all_patches = patches[bug_id]

        if os.path.exists('tmp'):
            shutil.rmtree('tmp')

        validation_results_path = os.path.join('validation_results', bug_id)
        create_patch_directories(validation_results_path)

        checkout_defects4j_project(project, bug_number, f'tmp/original_projects/{project}-{bug_number}')
        create_clones(all_patches, project, bug_number)

        validators = []
        validator_patches = []
        for thread in range(number_of_threads):
            validators.append(Validator(bug_id, bugs[bug_id], all_patches, validation_results_path, f'tmp/clones/{project}-{bug_number}'))
            validator_patches.append([])

        for patch_index, patch in enumerate(all_patches):
            validator_patches[patch_index % number_of_threads].append(patch_index)

        threads = []

        for thread in range(number_of_threads):
            thread = threading.Thread(target=validators[thread].validate_patches, args=(validator_patches[thread],))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

def create_patch_directories(validation_results_path):
    if not os.path.exists(os.path.join(validation_results_path, 'uncompilable')):
        os.makedirs(os.path.join(validation_results_path, 'uncompilable'))
    if not os.path.exists(os.path.join(validation_results_path, 'failing')):
        os.makedirs(os.path.join(validation_results_path, 'failing'))
    if not os.path.exists(os.path.join(validation_results_path, 'plausible')):
        os.makedirs(os.path.join(validation_results_path, 'plausible'))
        if not os.path.exists(os.path.join(validation_results_path, 'timeout')):
            os.makedirs(os.path.join(validation_results_path, 'timeout'))

def create_clones(all_patches, project, bug_number):
    for patch_index, patch in enumerate(all_patches):
        if not os.path.exists(f'tmp/clones/{project}-{bug_number}'):
            os.makedirs(f'tmp/clones/{project}-{bug_number}')
        copy_tree(f'tmp/original_projects/{project}-{bug_number}',
                  f'tmp/clones/{project}-{bug_number}/patch-{patch_index}')
def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', type=str, required=True, help='bug dataset path')
    parser.add_argument('-p', type=str, required=True, help='patches path')
    parser.add_argument('-t', type=str, required=True, help='number of threads')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_arguments()
    main()