import re

with open('server.py', 'r', encoding='utf-8') as f:
    text = f.read()

replacements = {
    'create_job': '"hiring_manager", "admin_it"',
    'update_job': '"hiring_manager", "admin_it"',
    'reextract_job': '"hiring_manager", "admin_it"',
    'add_criterion': '"hiring_manager", "admin_it"',
    'update_criterion': '"hiring_manager", "admin_it"',
    'delete_criterion': '"hiring_manager", "admin_it"',
    'update_education': '"hiring_manager", "admin_it"',
    'delete_job': '"hiring_manager", "admin_it"',
    'upload_cv': '"hr_recruiter", "hiring_manager", "admin_it"',
    'delete_candidate': '"hr_recruiter", "hiring_manager", "admin_it"',
    'rescreen_candidate': '"hr_recruiter", "hiring_manager", "admin_it"',
    'add_candidate_manual': '"hr_recruiter", "hiring_manager", "admin_it"',
    'screen_from_pool': '"hr_recruiter", "hiring_manager", "admin_it"',
    'update_decision': '"hr_recruiter", "hiring_manager", "admin_it"',
}

for func_name, new_roles in replacements.items():
    pattern = r'(async def ' + func_name + r'\b.*?require_roles\()([^\)]+)(\))'
    
    def replacer(match):
        return match.group(1) + new_roles + match.group(3)
        
    text, num_subs = re.subn(pattern, replacer, text, flags=re.DOTALL)
    if num_subs > 0:
        print(f'Updated {func_name}')
    else:
        print(f'Failed to update {func_name}')

with open('server.py', 'w', encoding='utf-8') as f:
    f.write(text)
