import argparse
import os
import json

def main():
    metrics = {}

    plausible_patch_frequency = compute_plausible_patch_frequency()
    for project in plausible_patch_frequency:
        if project != 'total':
            print(f'Project {project} has at least one plausible patch in {round(plausible_patch_frequency[project] * 100, 2)}% of attempts.')

    mrr = compute_mrr()
    for project in mrr:
        if project != 'total':
            print(
                f'Project {project} has an MRR of {round(mrr[project], 2)}.')
    print(f'MRR over all projects: {round(mrr["total"], 2)}')
    print(f'On average, each bug at least one plausible patch in {round(plausible_patch_frequency["total"] * 100, 2)}% of attempts.')

    for project in os.listdir(args.r):
        metrics[project] = {}
        metrics[project]['plausible_patch_frequency'] = plausible_patch_frequency[project]
        metrics[project]['mrr'] = mrr[project]

    metrics['total'] = {}
    metrics['total']['plausible_patch_frequency'] = plausible_patch_frequency['total']
    metrics['total']['mrr'] = mrr['total']

    with open(args.o, 'w') as f:
        json.dump(metrics, f, indent=2)


def compute_plausible_patch_frequency():
    plausible_patch_frequencies = {}
    total_plausible_patches = 0
    total_attempts = 0
    for project in os.listdir(args.r):
        project_plausible_patches = 0
        project_attempts = 0
        for bug in os.listdir(os.path.join(args.r, project)):
            for prompt in os.listdir(os.path.join(args.r, project, bug)):
                for result in os.listdir(os.path.join(args.r, project, bug, prompt)):
                    if result == 'plausible':
                        total_plausible_patches += 1
                        project_plausible_patches += 1
                total_attempts += 1
                project_attempts += 1
        plausible_patch_frequencies[project] = project_plausible_patches / project_attempts


    plausible_patch_frequencies['total'] = total_plausible_patches / total_attempts


    return plausible_patch_frequencies

def compute_mrr():
    mrr = {}
    total_rr_sum = 0
    total_attempts = 0
    for project in os.listdir(args.r):
        project_rr_sum = 0
        project_attempts = 0
        for bug in os.listdir(os.path.join(args.r, project)):
            for prompt in os.listdir(os.path.join(args.r, project, bug)):
                if 'plausible' in os.listdir(os.path.join(args.r, project, bug, prompt)):
                    first_patch = int(os.listdir(os.path.join(args.r, project, bug, prompt, 'plausible'))[0][6:-4]) + 1
                    rr = 1 / first_patch
                else:
                    rr = 0
                project_rr_sum += rr
                total_rr_sum += rr
                total_attempts += 1
                project_attempts += 1
        mrr[project] = project_rr_sum / project_attempts
    mrr['total'] = total_rr_sum / total_attempts

    return mrr




def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', type=str, required=True, help='results path')
    parser.add_argument('-o', type=str, required=True, help='output path')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_arguments()
    main()