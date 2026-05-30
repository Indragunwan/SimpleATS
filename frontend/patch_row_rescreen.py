with open('src/pages/JobDetail.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# Add state
if 'const [reprocessingIds, setReprocessingIds]' not in text:
    text = text.replace(
        'const [pageSize, setPageSize] = useState(15);',
        'const [pageSize, setPageSize] = useState(15);\n  const [reprocessingIds, setReprocessingIds] = useState(new Set());'
    )

# Add handleRescreenCandidate function
if 'const handleRescreenCandidate =' not in text:
    text = text.replace(
        '''  const handleDeleteCandidate = async (candidateId) => {''',
        '''  const handleRescreenCandidate = async (candidateId) => {
    setReprocessingIds((prev) => {
      const next = new Set(prev);
      next.add(candidateId);
      return next;
    });
    try {
      await api.post(`/jobs/${id}/candidates/${candidateId}/rescreen`);
      toast.success("Kandidat berhasil di-screen ulang");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal melakukan screen ulang");
    } finally {
      setReprocessingIds((prev) => {
        const next = new Set(prev);
        next.delete(candidateId);
        return next;
      });
    }
  };

  const handleDeleteCandidate = async (candidateId) => {'''
    )

# Add button in the action column next to Delete
# Let's find:
#                         {c.candidate_id && (
#                           <button
#                             onClick={(e) => {
#                               e.stopPropagation();
#                               handleDeleteCandidate(c.candidate_id);
#                             }}
# ...
#                           </button>
#                         )}

old_action_button = '''                        {c.candidate_id && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteCandidate(c.candidate_id);
                            }}
                            data-testid={`delete-candidate-${c.candidate_id}`}
                            className="text-xs px-2.5 py-1 rounded-sm border border-rose-200 text-rose-600 hover:bg-rose-50 hover:border-rose-300 transition-colors font-medium flex items-center justify-center"
                            title="Hapus Kandidat"
                          >
                            <Trash2 size={14} />
                          </button>
                        )}'''

new_action_button = '''                        {c.candidate_id && (
                          <>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRescreenCandidate(c.candidate_id);
                              }}
                              disabled={reprocessingIds.has(c.candidate_id)}
                              className="text-xs px-2.5 py-1 rounded-sm border border-zinc-300 text-zinc-700 hover:bg-zinc-50 hover:border-zinc-400 transition-colors font-medium flex items-center justify-center"
                              title="Proses Ulang"
                            >
                              <RotateCw size={14} className={reprocessingIds.has(c.candidate_id) ? "animate-spin" : ""} />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteCandidate(c.candidate_id);
                              }}
                              data-testid={`delete-candidate-${c.candidate_id}`}
                              className="text-xs px-2.5 py-1 rounded-sm border border-rose-200 text-rose-600 hover:bg-rose-50 hover:border-rose-300 transition-colors font-medium flex items-center justify-center"
                              title="Hapus Kandidat"
                            >
                              <Trash2 size={14} />
                            </button>
                          </>
                        )}'''

if 'handleRescreenCandidate(c.candidate_id)' not in text:
    text = text.replace(old_action_button, new_action_button)

with open('src/pages/JobDetail.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("JobDetail.jsx patched with row reload button.")
