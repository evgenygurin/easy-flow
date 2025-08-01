#!/usr/bin/env python3
import yaml
import os
import sys

def validate_github_actions_structure(filepath):
    """Validate GitHub Actions workflow or composite action structure"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = yaml.safe_load(f)
    
    errors = []
    warnings = []
    
    # Check if it's a workflow or action
    if 'jobs' in content:  # Workflow file
        # Check required fields
        if 'name' not in content:
            warnings.append('Missing workflow name')
        if 'on' not in content:
            errors.append('Missing trigger events (on:)')
            
        # Check jobs structure
        for job_name, job in content.get('jobs', {}).items():
            if 'runs-on' not in job:
                errors.append(f'Job {job_name}: missing runs-on')
            
            # Check steps
            steps = job.get('steps', [])
            for i, step in enumerate(steps):
                if 'uses' in step and 'run' in step:
                    errors.append(f'Job {job_name}, step {i+1}: cannot have both uses and run')
                elif 'uses' not in step and 'run' not in step:
                    errors.append(f'Job {job_name}, step {i+1}: must have either uses or run')
                    
                # Check for composite action usage without checkout
                if 'uses' in step and step['uses'].startswith('./'):
                    # Find if there's a checkout step before this
                    checkout_found = False
                    for prev_step in steps[:i]:
                        if 'uses' in prev_step and 'checkout@' in prev_step['uses']:
                            checkout_found = True
                            break
                    if not checkout_found:
                        errors.append(f'Job {job_name}, step {i+1}: local action {step["uses"]} used without prior checkout')
                        
    elif 'runs' in content:  # Composite action
        if 'name' not in content:
            warnings.append('Missing action name')
        if 'description' not in content:
            warnings.append('Missing action description')
            
        runs = content.get('runs', {})
        if runs.get('using') != 'composite':
            errors.append('Composite action must use "composite"')
            
    return errors, warnings

def validate_github_context_usage(filepath):
    """Check for proper GitHub context usage"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    errors = []
    warnings = []
    
    # Check for github.event.inputs usage outside workflow_dispatch
    if 'github.event.inputs' in content:
        errors.append('Found github.event.inputs - should use inputs instead')
    
    # Check for missing workflow_dispatch when inputs are used
    if 'inputs.' in content and 'workflow_dispatch:' not in content:
        warnings.append('Using inputs without workflow_dispatch trigger')
    
    return errors, warnings

def check_all_files():
    """Check all GitHub Actions files"""
    all_errors = []
    all_warnings = []
    
    # Check workflows
    if os.path.exists('.github/workflows'):
        for file in os.listdir('.github/workflows'):
            if file.endswith(('.yml', '.yaml')):
                filepath = f'.github/workflows/{file}'
                print(f'🔍 Checking {filepath}...')
                
                # Structure validation
                errors, warnings = validate_github_actions_structure(filepath)
                
                # Context validation
                ctx_errors, ctx_warnings = validate_github_context_usage(filepath)
                errors.extend(ctx_errors)
                warnings.extend(ctx_warnings)
                
                if errors:
                    print(f'  ❌ Errors: {len(errors)}')
                    for error in errors:
                        print(f'    - {error}')
                    all_errors.extend(errors)
                
                if warnings:
                    print(f'  ⚠️  Warnings: {len(warnings)}')
                    for warning in warnings:
                        print(f'    - {warning}')
                    all_warnings.extend(warnings)
                    
                if not errors and not warnings:
                    print(f'  ✅ No issues found')
    
    # Check composite actions
    if os.path.exists('.github/actions'):
        for root, dirs, files in os.walk('.github/actions'):
            for file in files:
                if file.endswith(('.yml', '.yaml')):
                    filepath = os.path.join(root, file)
                    print(f'🔍 Checking {filepath}...')
                    
                    errors, warnings = validate_github_actions_structure(filepath)
                    
                    if errors:
                        print(f'  ❌ Errors: {len(errors)}')
                        for error in errors:
                            print(f'    - {error}')
                        all_errors.extend(errors)
                    
                    if warnings:
                        print(f'  ⚠️  Warnings: {len(warnings)}')
                        for warning in warnings:
                            print(f'    - {warning}')
                        all_warnings.extend(warnings)
                        
                    if not errors and not warnings:
                        print(f'  ✅ No issues found')
    
    print(f'\n📊 Final Summary:')
    print(f'  ❌ Total Errors: {len(all_errors)}')
    print(f'  ⚠️  Total Warnings: {len(all_warnings)}')
    
    if all_errors:
        print(f'\n🚨 Critical Issues Found:')
        for error in sorted(set(all_errors)):
            print(f'  - {error}')
    
    if all_warnings:
        print(f'\n⚠️  Warnings Found:')
        for warning in sorted(set(all_warnings)):
            print(f'  - {warning}')
    
    return len(all_errors) == 0

if __name__ == '__main__':
    result = check_all_files()
    print(f'\n🎯 Overall Result: {"PASSED" if result else "FAILED"}')
    sys.exit(0 if result else 1)