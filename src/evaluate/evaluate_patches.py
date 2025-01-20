import os
import json
import argparse
import threading
import shutil
import subprocess
import random

from tqdm import tqdm
from subprocess import TimeoutExpired
from concurrent.futures import ThreadPoolExecutor
from enum import Enum

class CompileError(Exception):
    def __init__(self, message):
        super().__init__(message)

class TestError(Exception):
    def __init__(self, message):
        super().__init__(message)

class EvaluationResult(Enum):
    PLAUSIBLE = 'plausible'
    FAILING = 'failing'
    UNCOMPILABLE = 'uncompilable'
    FAILED_TEST_EXECUTION = 'failed_test_execution'
    TIMEOUT = 'timeout'

class Patch:
    def __init__(self, prompt_index: int, patch_index: int, function: str):
        self.prompt_index = prompt_index
        self.patch_index = patch_index
        self.function = function

class Bug:
    def __init__(self, bug: dict, checkout_lock: threading.Lock):
        self.id = bug['id']
        self.bug = bug
        self.project = bug['project']
        self.number = bug['number']
        self.replacement_info = bug['replacement_info']
        self.checkout_lock = checkout_lock

class PatchEvaluation:

    def __init__(self, bug: Bug, patch: Patch, working_directory: str):
        self.result = None
        self.future = None
        self.patch = patch
        self.bug = bug
        self.working_directory = working_directory
        self.original_directory = os.path.join(self.working_directory, bug.id, 'original')
        self.clone_directory = os.path.join(self.working_directory, bug.id, 'clones', f'prompt-{self.patch.prompt_index}', f'patch-{self.patch.patch_index}')
        self.results_path = args.r

    def start(self, executor):
        self.future = executor.submit(self.evaluate)

    def evaluate(self):
        self.copy_project()
        self.apply_patch()
        self.compile_project()
        self.test_project()
        return self.passes_tests()

    def copy_project(self):
        with self.bug.checkout_lock:
            if not os.path.exists(self.original_directory):
                self.checkout_project()
        shutil.copytree(self.original_directory, self.clone_directory, dirs_exist_ok=True)

    def checkout_project(self):
        command = ["defects4j", "checkout", "-p", self.bug.project, "-v", f"{self.bug.number}b", "-w",
                   self.original_directory]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr)

    def apply_patch(self):
        project_file = self.bug.replacement_info['file']
        first_line = self.bug.replacement_info['first_line']
        last_line = self.bug.replacement_info['last_line']

        file_path = os.path.join(self.clone_directory, project_file)
        with open(file_path, 'r', encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = lines[:first_line - 1] + self.patch.function.splitlines(keepends=True) + lines[last_line:]

        with open(file_path, 'w', encoding="utf-8") as f:
            f.writelines(new_lines)

    def compile_project(self):
        command = ["defects4j", "compile", '-w', self.clone_directory]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10 * 60)
        if result.returncode != 0:
            raise CompileError(result.stderr)

    def test_project(self):
        command = ["defects4j", "test", '-w', self.clone_directory]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10 * 60)
        if result.returncode != 0:
            raise TestError(result.stderr)

    def passes_tests(self):
        with open(os.path.join(self.clone_directory, 'failing_tests'), 'r') as f:
            return f.read() == ""

    def await_result(self):
        try:
            print(f"awaiting bug: {self.bug.id}, patch {self.patch.prompt_index}-{self.patch.patch_index}")
            passes_tests = self.future.result(timeout=15*60)
            if passes_tests:
                self.result = EvaluationResult.PLAUSIBLE
            else:
                self.result = EvaluationResult.FAILING
        except CompileError:
            self.result = EvaluationResult.UNCOMPILABLE
        except TestError:
            self.result = EvaluationResult.FAILED_TEST_EXECUTION
        except (TimeoutError, TimeoutExpired):
            self.result = EvaluationResult.TIMEOUT

    def write_result(self):
        path = os.path.join(self.results_path,
                            self.bug.project,
                            self.bug.number,
                            f'prompt-{self.patch.prompt_index}',
                            self.result.value,
                            f'patch-{self.patch.patch_index}.txt')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(self.patch.function)

    def clean(self):
        safe_remove(self.clone_directory)



def main():
    bugs_path = args.b
    patches_path = args.p
    number_of_threads = args.t

    with open(bugs_path, 'r') as f:
        bugs = json.load(f)
    with open(patches_path, 'r') as f:
        patches = json.load(f)

    bug_checkout_locks = create_bug_checkout_locks(bugs)

    working_directory = 'tmp'
    print('Cleaning up working directory...')
    safe_remove(working_directory)
    print('Done!')

    patch_evaluation_queue = create_evaluation_queue(bugs, patches, working_directory, bug_checkout_locks)

    with ThreadPoolExecutor(max_workers=number_of_threads) as executor:
        for patch_evaluation in patch_evaluation_queue:
            patch_evaluation.start(executor)

        for patch_evaluation in tqdm(patch_evaluation_queue):
            patch_evaluation.await_result()
            patch_evaluation.write_result()
            patch_evaluation.clean()

    safe_remove(working_directory)

def create_bug_checkout_locks(bugs):
    locks = {}
    for bug_id in bugs:
        if bug_id not in locks:
            locks[bug_id] = threading.Lock()
    return locks

def create_evaluation_queue(bugs, patches, working_directory, locks):
    queue = []
    for bug_id in bugs:
        bug_patches = patches[bug_id]
        for prompt_index, prompt_patches in enumerate(bug_patches):
            for patch_index, patched_function in enumerate(prompt_patches):
                patch = Patch(prompt_index, patch_index, patched_function)
                bug = Bug(bugs[bug_id], locks[bug_id])
                queue.append(PatchEvaluation(bug, patch, working_directory))
    # Reduces wait for checkout during execution.
    random.shuffle(queue)
    return queue

def safe_remove(path):
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', type=str, required=True, help='bug dataset path')
    parser.add_argument('-p', type=str, required=True, help='patches path')
    parser.add_argument('-r', type=str, required=True, help='results path')
    parser.add_argument('-t', type=int, required=True, help='number of threads')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_arguments()
    main()