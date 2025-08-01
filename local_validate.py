#!/usr/bin/env python3
"""
Local GitHub Actions validator using Python AST and YAML parsing
"""
import yaml
import os
import sys
import re
import json
from pathlib import Path

def validate_yaml_syntax(filepath):
    """Validate YAML syntax"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            # Handle 'on' keyword which can be parsed as boolean True
            yaml_content = yaml.safe_load(content)
        return True, None, yaml_content
    except yaml.YAMLError as e:
        return False, f"YAML Error: {e}", None
    except Exception as e:
        return False, f"Error: {e}", None

def validate_workflow_structure(filepath, content):
    """Validate GitHub Actions workflow structure"""
    errors = []
    warnings = []
    
    # Check required top-level fields
    if 'name' not in content:
        warnings.append("Missing workflow 'name'")
    
    # Check for trigger events (on: can be parsed as True in YAML)
    has_triggers = 'on' in content or True in content
    if not has_triggers:
        errors.append("Missing trigger events ('on:')")
    
    # Validate jobs
    if 'jobs' not in content:
        errors.append("Missing 'jobs' section")
        return errors, warnings
    
    jobs = content['jobs']
    for job_name, job_config in jobs.items():
        if not isinstance(job_config, dict):
            errors.append(f"Job '{job_name}' must be a dictionary")
            continue
            
        # Check required job fields
        if 'runs-on' not in job_config:
            errors.append(f"Job '{job_name}' missing 'runs-on'")
        
        # Validate steps
        steps = job_config.get('steps', [])
        for i, step in enumerate(steps):
            step_num = i + 1
            
            if not isinstance(step, dict):
                errors.append(f"Job '{job_name}', step {step_num}: must be a dictionary")
                continue
            
            # Each step must have either 'uses' or 'run'
            has_uses = 'uses' in step
            has_run = 'run' in step
            
            if has_uses and has_run:
                errors.append(f"Job '{job_name}', step {step_num}: cannot have both 'uses' and 'run'")
            elif not has_uses and not has_run:
                errors.append(f"Job '{job_name}', step {step_num}: must have either 'uses' or 'run'")
            
            # Check for local actions without prior checkout
            if has_uses and step['uses'].startswith('./'):
                checkout_found = False
                for prev_step in steps[:i]:
                    if 'uses' in prev_step and 'checkout@' in prev_step['uses']:
                        checkout_found = True
                        break
                if not checkout_found:
                    errors.append(f"Job '{job_name}', step {step_num}: local action '{step['uses']}' used without prior checkout")
    
    return errors, warnings

def validate_composite_action(filepath, content):
    """Validate composite action structure"""
    errors = []
    warnings = []
    
    # Check required fields
    if 'name' not in content:
        warnings.append("Missing action 'name'")
    if 'description' not in content:
        warnings.append("Missing action 'description'")
    
    # Check runs section
    if 'runs' not in content:
        errors.append("Missing 'runs' section")
        return errors, warnings
    
    runs = content['runs']
    if 'using' not in runs:
        errors.append("Missing 'using' in runs section")
    elif runs['using'] != 'composite':
        errors.append(f"Expected 'using: composite', got 'using: {runs['using']}'")
    
    # Validate steps in composite action
    steps = runs.get('steps', [])
    for i, step in enumerate(steps):
        if 'shell' not in step and 'uses' not in step:
            errors.append(f"Step {i+1}: composite action steps must have 'shell' when using 'run'")
    
    return errors, warnings

def check_security_issues(filepath, content_text):
    """Check for common security issues"""
    warnings = []
    errors = []
    
    # Check for potential hardcoded secrets
    secret_patterns = [
        r'ghp_[a-zA-Z0-9]{36}',  # GitHub personal access tokens
        r'github_pat_[a-zA-Z0-9_]{82}',  # GitHub fine-grained tokens
        r'sk-[a-zA-Z0-9]{48}',  # OpenAI API keys (example)
    ]
    
    for pattern in secret_patterns:
        if re.search(pattern, content_text):
            errors.append(f"Potential hardcoded secret found matching pattern: {pattern}")
    
    # Check for shell injection vulnerabilities
    injection_patterns = [
        r'\$\{\{.*github\.event\.issue\.title.*\}\}',
        r'\$\{\{.*github\.event\.comment\.body.*\}\}',
        r'\$\{\{.*github\.event\.pull_request\.title.*\}\}',
    ]
    
    for pattern in injection_patterns:
        if re.search(pattern, content_text):
            warnings.append(f"Potential shell injection vulnerability: {pattern}")
    
    return errors, warnings

def check_best_practices(filepath, content):
    """Check GitHub Actions best practices"""
    warnings = []
    
    # Check for unpinned action versions
    if 'jobs' in content:
        for job_name, job_config in content['jobs'].items():
            steps = job_config.get('steps', [])
            for step in steps:
                if 'uses' in step:
                    action = step['uses']
                    if '@main' in action or '@master' in action:
                        warnings.append(f"Unpinned action version in job '{job_name}': {action}")
    
    # Check for timeout settings
    if 'jobs' in content:
        for job_name, job_config in content['jobs'].items():
            if 'timeout-minutes' not in job_config:
                warnings.append(f"Job '{job_name}' missing timeout-minutes")
    
    return warnings

def validate_file(filepath):
    """Validate a single GitHub Actions file"""
    print(f"🔍 Validating {filepath}")
    
    # Read and parse YAML
    valid, error, content = validate_yaml_syntax(filepath)
    if not valid:
        print(f"  ❌ YAML Syntax Error: {error}")
        return False
    
    # Read raw content for security checks
    with open(filepath, 'r', encoding='utf-8') as f:
        raw_content = f.read()
    
    all_errors = []
    all_warnings = []
    
    # Determine file type and validate accordingly
    if 'jobs' in content:
        # Workflow file
        errors, warnings = validate_workflow_structure(filepath, content)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        
        # Best practices check
        bp_warnings = check_best_practices(filepath, content)
        all_warnings.extend(bp_warnings)
        
    elif 'runs' in content:
        # Composite action
        errors, warnings = validate_composite_action(filepath, content)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
    
    # Security checks
    sec_errors, sec_warnings = check_security_issues(filepath, raw_content)
    all_errors.extend(sec_errors)
    all_warnings.extend(sec_warnings)
    
    # Report results
    if all_errors:
        print(f"  ❌ Errors ({len(all_errors)}):")
        for error in all_errors:
            print(f"    - {error}")
    
    if all_warnings:
        print(f"  ⚠️  Warnings ({len(all_warnings)}):")
        for warning in all_warnings:
            print(f"    - {warning}")
    
    if not all_errors and not all_warnings:
        print(f"  ✅ No issues found")
    
    return len(all_errors) == 0

def main():
    """Main validation function"""
    print("🚀 Starting GitHub Actions local validation")
    print("=" * 50)
    
    success_count = 0
    total_count = 0
    failed_files = []
    
    # Validate workflows
    workflows_dir = Path('.github/workflows')
    if workflows_dir.exists():
        for yaml_file in workflows_dir.glob('*.yml'):
            total_count += 1
            if validate_file(yaml_file):
                success_count += 1
            else:
                failed_files.append(str(yaml_file))
            print()
    
    # Validate composite actions
    actions_dir = Path('.github/actions')
    if actions_dir.exists():
        for yaml_file in actions_dir.rglob('*.yml'):
            total_count += 1
            if validate_file(yaml_file):
                success_count += 1
            else:
                failed_files.append(str(yaml_file))
            print()
    
    # Summary
    print("=" * 50)
    print(f"📊 Validation Summary:")
    print(f"  ✅ Passed: {success_count}/{total_count}")
    print(f"  ❌ Failed: {len(failed_files)}")
    
    if failed_files:
        print(f"\n🚨 Failed files:")
        for filepath in failed_files:
            print(f"  - {filepath}")
        return False
    else:
        print(f"\n🎉 All {total_count} files passed validation!")
        return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)