import re

with open('src/pages/JobDetail.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. import useAuth
if 'import { useAuth }' not in text:
    text = text.replace(
        'import api, { BAND_COLORS, RECOMMENDATION_LABELS, SCORE_BAND } from "@/lib/api";',
        'import { useAuth } from "@/context/AuthContext";\nimport api, { BAND_COLORS, RECOMMENDATION_LABELS, SCORE_BAND } from "@/lib/api";'
    )

# 2. const { user }
if 'const { user }' not in text:
    text = text.replace(
        'const navigate = useNavigate();\n',
        'const navigate = useNavigate();\n  const { user } = useAuth();\n'
    )

# 3. startEditingHeader
if 'user?.role !== "hr_recruiter"' not in text.split('startEditingHeader')[0][-100:]:
    text = text.replace(
        '{!editingHeader ? (\n              <div className="group relative">\n                <h1 className="font-heading text-2xl font-semibold tracking-tight text-zinc-900">{job.title}</h1>\n                {job.target_position && (\n                  <p className="text-sm text-zinc-500 mt-1">\n                    <span className="text-zinc-400 font-medium">Tanggung jawab utama:</span> {job.target_position}\n                  </p>\n                )}\n                <button\n                  onClick={startEditingHeader}',
        '{!editingHeader ? (\n              <div className="group relative">\n                <h1 className="font-heading text-2xl font-semibold tracking-tight text-zinc-900">{job.title}</h1>\n                {job.target_position && (\n                  <p className="text-sm text-zinc-500 mt-1">\n                    <span className="text-zinc-400 font-medium">Tanggung jawab utama:</span> {job.target_position}\n                  </p>\n                )}\n                {user?.role !== "hr_recruiter" && (\n                  <button\n                    onClick={startEditingHeader}'
    )
    # also add closing brace for that button
    text = text.replace(
        '                  > Edit\n                </button>\n              </div>\n            )}',
        '                  > Edit\n                  </button>\n                )}\n              </div>\n            )}'
    )
    
    # Wait, the code around startEditingHeader might be different. Let's do a regex replace
    text = re.sub(
        r'(<button[^>]*onClick=\{startEditingHeader\}[^>]*>.*?</button>)',
        r'{user?.role !== "hr_recruiter" && (\n                  \1\n                )}',
        text,
        flags=re.DOTALL
    )

# 4. Hapus Lowongan and Ekstrak Ulang
text = re.sub(
    r'(<Button[^>]*onClick=\{handleReextract\}.*?</Button>)',
    r'{user?.role !== "hr_recruiter" && (\n              \1\n            )}',
    text,
    flags=re.DOTALL
)

text = re.sub(
    r'(<Button[^>]*onClick=\{handleDeleteJob\}.*?</Button>)',
    r'{user?.role !== "hr_recruiter" && (\n              \1\n            )}',
    text,
    flags=re.DOTALL
)

text = re.sub(
    r'(<Button[^>]*onClick=\{startEditingMeta\}.*?</Button>)',
    r'{user?.role !== "hr_recruiter" && (\n              \1\n            )}',
    text,
    flags=re.DOTALL
)

# 5. CriteriaEditor
text = re.sub(
    r'<CriteriaEditor job=\{job\} onUpdate=\{load\} />',
    r'<CriteriaEditor job={job} onUpdate={load} editable={user?.role !== "hr_recruiter"} />',
    text
)

with open('src/pages/JobDetail.jsx', 'w', encoding='utf-8') as f:
    f.write(text)
