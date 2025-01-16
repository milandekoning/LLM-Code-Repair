import argparse
import os
import json

def main():
    plausible_patch_frequency = compute_plausible_patch_frequency()
    mrr = compute_mrr()

    print_plausible_patch_frequency(plausible_patch_frequency)
    print_mrr(mrr)

    print(f'On average, each bug at least one plausible patch in {round(plausible_patch_frequency["total"] * 100, 2)}% of attempts.')
    print(f'MRR over all projects: {round(mrr["total"], 2)}')

    metrics = combine_metrics(plausible_patch_frequency, mrr)

    with open(args.o, 'w') as f:
        json.dump(metrics, f, indent=2)

def compute_plausible_patch_frequency():
    plausible_patch_frequencies = {}
    total_plausible_patches = 0
    total_attempts = 0
    for project in os.listdir(args.r):
        plausible_patches, attempts = get_plausible_counts(project)
        plausible_patch_frequencies[project] = plausible_patches / attempts
        total_plausible_patches += plausible_patches
        total_attempts += attempts

    plausible_patch_frequencies['total'] = total_plausible_patches / total_attempts

    return plausible_patch_frequencies

def get_plausible_counts(project: str):
    plausible_patches = 0
    attempts = 0
    for bug in os.listdir(os.path.join(args.r, project)):
        for prompt in os.listdir(os.path.join(args.r, project, bug)):
            for result in os.listdir(os.path.join(args.r, project, bug, prompt)):
                if result == 'plausible':
                    plausible_patches += 1
            attempts += 1
    return plausible_patches, attempts

def compute_mrr():
    mrr = {}
    total_rr_sum = 0
    total_attempts = 0
    for project in os.listdir(args.r):
        rr_sum, attempts = get_project_sum_rr(project)
        mrr[project] = rr_sum / attempts
        total_rr_sum += rr_sum
        total_attempts += attempts

    mrr['total'] = total_rr_sum / total_attempts

    return mrr

def get_project_sum_rr(project: str):
    rr_sum = 0
    attempts = 0
    for bug in os.listdir(os.path.join(args.r, project)):
        for prompt in os.listdir(os.path.join(args.r, project, bug)):
            if 'plausible' in os.listdir(os.path.join(args.r, project, bug, prompt)):
                first_patch_number = int(os.listdir(os.path.join(args.r, project, bug, prompt, 'plausible'))[0][6:-4]) + 1
                rr = 1 / first_patch_number
            else:
                rr = 0
            rr_sum += rr
            attempts += 1

    return rr_sum, attempts

def print_plausible_patch_frequency(plausible_patch_frequency):
    for project in plausible_patch_frequency:
        if project != 'total':
            print(f'Project {project} has at least one plausible patch in {round(plausible_patch_frequency[project] * 100, 2)}% of attempts.')

def print_mrr(mrr):
    for project in mrr:
        if project != 'total':
            print(
                f'Project {project} has an MRR of {round(mrr[project], 2)}.')

def combine_metrics(plausible_patch_frequency, mrr):
    metrics = {}

    for project in os.listdir(args.r):
        metrics[project] = {}
        metrics[project]['plausible_patch_frequency'] = plausible_patch_frequency[project]
        metrics[project]['mrr'] = mrr[project]

    metrics['total'] = {}
    metrics['total']['plausible_patch_frequency'] = plausible_patch_frequency['total']
    metrics['total']['mrr'] = mrr['total']

    return metrics

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', type=str, required=True, help='results path')
    parser.add_argument('-o', type=str, required=True, help='output path')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_arguments()
    main()