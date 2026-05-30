import re

def patch_job_detail():
    with open('src/pages/JobDetail.jsx', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Add TABS definition and missing icons
    if 'const TABS =' not in text:
        text = text.replace(
            'export default function JobDetail() {',
            'const TABS = [\n  { id: "criteria", label: "Kriteria & Bobot", icon: Settings2 },\n  { id: "candidates", label: "Kandidat & Ranking", icon: Users },\n];\n\nexport default function JobDetail() {'
        )
        
    if 'Settings2' not in text:
        text = text.replace('Trash2,', 'Trash2, Settings2, Users,')

    # 2. Add activeTab state
    if 'const [activeTab' not in text:
        text = text.replace(
            'const [candidates, setCandidates] = useState([]);',
            'const [candidates, setCandidates] = useState([]);\n  const [activeTab, setActiveTab] = useState("criteria");'
        )

    # 3. Insert Tab UI and conditional rendering
    # We find where `<header>` ends.
    # The header ends with `</header>`
    header_end = text.find('</header>') + len('</header>')
    
    # We find where `{/* Criteria & Education Editor */}` starts
    criteria_start = text.find('{/* Criteria & Education Editor */}')
    
    # We find where `{/* Candidates */}` starts
    cands_start = text.find('{/* Candidates */}')
    
    # We find where `</div>\n    </div>\n  );\n}` starts at the very end.
    # The page ends with:
    #         </table>
    #       </div>
    #     </div>
    #   );
    # }
    
    # To be safe, we wrap the criteria and candidates in the activeTab condition.
    
    # The new UI to insert after </header>
    tab_ui = """
      {/* Tab Navigation */}
      <div className="flex items-center gap-0 border-b border-zinc-200 mb-6">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                relative flex items-center gap-2 px-5 py-3 text-sm font-medium transition-all
                ${isActive
                  ? "text-zinc-900 border-b-2 border-zinc-900 -mb-px bg-transparent"
                  : "text-zinc-500 hover:text-zinc-700 border-b-2 border-transparent -mb-px"
                }
              `}
              data-testid={`tab-${tab.id}`}
            >
              <Icon size={15} className={isActive ? "text-zinc-900" : "text-zinc-400"} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {activeTab === "criteria" ? (
"""
    
    middle_ui = """
      ) : (
"""
    
    end_ui = """
      )}
"""
    
    if '{/* Tab Navigation */}' not in text:
        # Before criteria, insert tab_ui
        text = text[:criteria_start] + tab_ui + text[criteria_start:cands_start] + middle_ui + text[cands_start:]
        
        # Now we need to insert the closing `)}` just before the final `</div>\n  );\n}`
        # Let's find the final `</div>` before `);\n}`
        end_idx = text.rfind('</div>\n  );\n}')
        if end_idx != -1:
            text = text[:end_idx] + end_ui + text[end_idx:]

    with open('src/pages/JobDetail.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    
    print("Patched JobDetail.jsx successfully.")

if __name__ == '__main__':
    patch_job_detail()
