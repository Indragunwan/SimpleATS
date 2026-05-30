import os

# --- PATCH SCREENING DETAIL ---
with open('src/pages/ScreeningDetail.jsx', 'r', encoding='utf-8') as f:
    sd_content = f.read()

# Add RotateCw import
if 'RotateCw' not in sd_content:
    sd_content = sd_content.replace(
        'import { ArrowLeft, Check, X, Pause, Mail, Phone, FileText, Trash2 } from "lucide-react";',
        'import { ArrowLeft, Check, X, Pause, Mail, Phone, FileText, Trash2, RotateCw } from "lucide-react";'
    )

# Add rescreening state
if 'const [rescreening, setRescreening]' not in sd_content:
    sd_content = sd_content.replace(
        'const [data, setData] = useState(null);',
        'const [data, setData] = useState(null);\n  const [rescreening, setRescreening] = useState(false);'
    )

# Add handleRescreen function
if 'const handleRescreen =' not in sd_content:
    sd_content = sd_content.replace(
        'const { screening: s, candidate: c, job } = data;',
        'const { screening: s, candidate: c, job } = data;\n\n  const handleRescreen = async () => {\n    setRescreening(true);\n    try {\n      await api.post(`/jobs/${job.id}/candidates/${c.id}/rescreen`);\n      toast.success("Kandidat berhasil di-screen ulang");\n      load();\n    } catch (err) {\n      toast.error(err?.response?.data?.detail || "Gagal melakukan screen ulang");\n    } finally {\n      setRescreening(false);\n    }\n  };'
    )

# Add Reload/Process button next to Delete
if 'data-testid="rescreen-candidate"' not in sd_content:
    sd_content = sd_content.replace(
        '''          <Button
            onClick={handleDelete}
            variant="outline"
            className="rounded-sm border-rose-200 text-rose-600 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-300 ml-2 font-semibold"
            size="sm"
            data-testid="delete-screening"
          >
            <Trash2 size={14} className="mr-1" /> Hapus Screening
          </Button>''',
        '''          <Button
            onClick={handleRescreen}
            disabled={rescreening}
            variant="outline"
            className="rounded-sm border-zinc-300 text-zinc-700 hover:bg-zinc-50 hover:border-zinc-400 ml-2 font-semibold"
            size="sm"
            data-testid="rescreen-candidate"
          >
            <RotateCw size={14} className={`mr-1 ${rescreening ? "animate-spin" : ""}`} />
            {rescreening ? "Memproses..." : "Proses Ulang"}
          </Button>
          <Button
            onClick={handleDelete}
            variant="outline"
            className="rounded-sm border-rose-200 text-rose-600 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-300 ml-2 font-semibold"
            size="sm"
            data-testid="delete-screening"
          >
            <Trash2 size={14} className="mr-1" /> Hapus Screening
          </Button>'''
    )

with open('src/pages/ScreeningDetail.jsx', 'w', encoding='utf-8') as f:
    f.write(sd_content)
print("ScreeningDetail.jsx patched.")


# --- PATCH JOB DETAIL ---
with open('src/pages/JobDetail.jsx', 'r', encoding='utf-8') as f:
    jd_content = f.read()

# Add useLocation import and Chevron sort icons from lucide-react if needed (or we can use simple triangles)
if 'useLocation' not in jd_content:
    jd_content = jd_content.replace(
        'import { useNavigate, useParams } from "react-router-dom";',
        'import { useNavigate, useParams, useLocation } from "react-router-dom";'
    )

# Add ChevronUp and ChevronDown imports if we want to display nice sorting indicators
# Wait, let's look at lucide-react imports:
if 'ChevronUp' not in jd_content:
    jd_content = jd_content.replace(
        'import { ArrowLeft, Upload, RotateCw, Briefcase, Search, Sparkles, Trash2, HelpCircle, Pencil, Save, X, Settings2, Users } from "lucide-react";',
        'import { ArrowLeft, Upload, RotateCw, Briefcase, Search, Sparkles, Trash2, HelpCircle, Pencil, Save, X, Settings2, Users, ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";'
    )

# Initialize activeTab from location state
jd_content = jd_content.replace(
    'const [activeTab, setActiveTab] = useState("criteria");',
    '''const location = useLocation();
  const [activeTab, setActiveTab] = useState(location.state?.activeTab || "criteria");
  const [sortConfig, setSortConfig] = useState({ key: "total_score", direction: "desc" });
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);

  const handleSort = (key) => {
    let direction = "asc";
    if (sortConfig.key === key && sortConfig.direction === "asc") {
      direction = "desc";
    }
    setSortConfig({ key, direction });
    setCurrentPage(1);
  };'''
)

# Reset currentPage on filter changes
jd_content = jd_content.replace(
    'const fileInputRef = useRef(null);',
    '''const fileInputRef = useRef(null);
  useEffect(() => {
    setCurrentPage(1);
  }, [search, minScore]);'''
)

# Replace sorted candidates logic
jd_content = jd_content.replace(
    '''  const filtered = candidates.filter(
    (c) =>
      (c.total_score || 0) >= minScore &&
      (search === "" ||
        (c.candidate_name || "").toLowerCase().includes(search.toLowerCase()))
  );''',
    '''  const filtered = candidates.filter(
    (c) =>
      (c.total_score || 0) >= minScore &&
      (search === "" ||
        (c.candidate_name || "").toLowerCase().includes(search.toLowerCase()))
  );

  const sortedCandidates = [...filtered].sort((a, b) => {
    let valA, valB;
    if (sortConfig.key === "candidate_name") {
      valA = a.candidate_name || "";
      valB = b.candidate_name || "";
    } else if (sortConfig.key === "total_score") {
      valA = a.total_score || 0;
      valB = b.total_score || 0;
    } else if (sortConfig.key === "must_have") {
      valA = a.must_have?.score || 0;
      valB = b.must_have?.score || 0;
    } else if (sortConfig.key === "experience") {
      valA = a.experience?.score || 0;
      valB = b.experience?.score || 0;
    } else if (sortConfig.key === "recommendation") {
      valA = a.recommendation || "";
      valB = b.recommendation || "";
    } else if (sortConfig.key === "decision") {
      valA = a.decision || "";
      valB = b.decision || "";
    }

    if (typeof valA === "string") {
      return sortConfig.direction === "asc"
        ? valA.localeCompare(valB)
        : valB.localeCompare(valA);
    } else {
      return sortConfig.direction === "asc"
        ? (valA || 0) - (valB || 0)
        : (valB || 0) - (valA || 0);
    }
  });

  const startIndex = (currentPage - 1) * pageSize;
  const paginatedCandidates = sortedCandidates.slice(startIndex, startIndex + pageSize);
  const totalPages = Math.ceil(sortedCandidates.length / pageSize);'''
)

# Replace table head rows
jd_content = jd_content.replace(
    '''            <tr className="text-left">
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide w-10">#</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Kandidat</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-center">Skor</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Must</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Pengalaman</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Rekomendasi</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Keputusan</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-right">Aksi</th>
            </tr>''',
    '''            <tr className="text-left">
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide w-10">#</th>
              <th 
                className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide cursor-pointer hover:bg-zinc-100/80 transition-colors select-none"
                onClick={() => handleSort("candidate_name")}
              >
                <div className="flex items-center gap-1">
                  <span>Kandidat</span>
                  {sortConfig.key === "candidate_name" ? (
                    sortConfig.direction === "asc" ? <ChevronUp size={12} /> : <ChevronDown size={12} />
                  ) : <ChevronsUpDown size={12} className="opacity-40" />}
                </div>
              </th>
              <th 
                className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide cursor-pointer hover:bg-zinc-100/80 transition-colors select-none text-center"
                onClick={() => handleSort("total_score")}
              >
                <div className="flex items-center justify-center gap-1">
                  <span>Skor</span>
                  {sortConfig.key === "total_score" ? (
                    sortConfig.direction === "asc" ? <ChevronUp size={12} /> : <ChevronDown size={12} />
                  ) : <ChevronsUpDown size={12} className="opacity-40" />}
                </div>
              </th>
              <th 
                className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide cursor-pointer hover:bg-zinc-100/80 transition-colors select-none"
                onClick={() => handleSort("must_have")}
              >
                <div className="flex items-center gap-1">
                  <span>Must</span>
                  {sortConfig.key === "must_have" ? (
                    sortConfig.direction === "asc" ? <ChevronUp size={12} /> : <ChevronDown size={12} />
                  ) : <ChevronsUpDown size={12} className="opacity-40" />}
                </div>
              </th>
              <th 
                className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide cursor-pointer hover:bg-zinc-100/80 transition-colors select-none"
                onClick={() => handleSort("experience")}
              >
                <div className="flex items-center gap-1">
                  <span>Pengalaman</span>
                  {sortConfig.key === "experience" ? (
                    sortConfig.direction === "asc" ? <ChevronUp size={12} /> : <ChevronDown size={12} />
                  ) : <ChevronsUpDown size={12} className="opacity-40" />}
                </div>
              </th>
              <th 
                className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide cursor-pointer hover:bg-zinc-100/80 transition-colors select-none"
                onClick={() => handleSort("recommendation")}
              >
                <div className="flex items-center gap-1">
                  <span>Rekomendasi</span>
                  {sortConfig.key === "recommendation" ? (
                    sortConfig.direction === "asc" ? <ChevronUp size={12} /> : <ChevronDown size={12} />
                  ) : <ChevronsUpDown size={12} className="opacity-40" />}
                </div>
              </th>
              <th 
                className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide cursor-pointer hover:bg-zinc-100/80 transition-colors select-none"
                onClick={() => handleSort("decision")}
              >
                <div className="flex items-center gap-1">
                  <span>Keputusan</span>
                  {sortConfig.key === "decision" ? (
                    sortConfig.direction === "asc" ? <ChevronUp size={12} /> : <ChevronDown size={12} />
                  ) : <ChevronsUpDown size={12} className="opacity-40" />}
                </div>
              </th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-right w-24">Aksi</th>
            </tr>'''
)

# Update data description info above table:
jd_content = jd_content.replace(
    '''            <p className="text-xs text-zinc-500 mt-0.5">
              {candidates.length} total · {filtered.length} ditampilkan
            </p>''',
    '''            <p className="text-xs text-zinc-500 mt-0.5">
              {candidates.length} total · {filtered.length} ditemukan
            </p>'''
)

# Add Page Size select
jd_content = jd_content.replace(
    '''            <select
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="border border-zinc-300 rounded-sm text-xs h-8 px-2"
              data-testid="min-score-filter"
            >
              <option value={0}>Semua skor</option>
              <option value={40}>Min 40</option>
              <option value={60}>Min 60</option>
              <option value={75}>Min 75 (Shortlist)</option>
            </select>''',
    '''            <select
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="border border-zinc-300 rounded-sm text-xs h-8 px-2"
              data-testid="min-score-filter"
            >
              <option value={0}>Semua skor</option>
              <option value={40}>Min 40</option>
              <option value={60}>Min 60</option>
              <option value={75}>Min 75 (Shortlist)</option>
            </select>
            <div className="flex items-center gap-1.5 ml-2">
              <span className="text-xs text-zinc-500">Tampilkan:</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setCurrentPage(1);
                }}
                className="border border-zinc-300 rounded-sm text-xs h-8 px-2"
              >
                <option value={10}>10 data</option>
                <option value={15}>15 data</option>
                <option value={30}>30 data</option>
                <option value={50}>50 data</option>
              </select>
            </div>'''
)

# Update filtered.map and index mapping:
jd_content = jd_content.replace(
    'filtered.length === 0 ? (',
    'paginatedCandidates.length === 0 ? ('
)

# Also update the index calculation in the list rendering:
jd_content = jd_content.replace(
    '<td className="px-5 py-3 text-xs text-zinc-400 font-mono tabular-nums">{idx + 1}</td>',
    '<td className="px-5 py-3 text-xs text-zinc-400 font-mono tabular-nums">{startIndex + idx + 1}</td>'
)

jd_content = jd_content.replace(
    'filtered.map((c, idx) => {',
    'paginatedCandidates.map((c, idx) => {'
)

# Add Pagination controls below the table:
jd_content = jd_content.replace(
    '''        </table>
      </div>
      )}''',
    '''        </table>
        
        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="px-5 py-3 border-t border-zinc-100 flex items-center justify-between gap-3 bg-zinc-50/30">
            <span className="text-xs text-zinc-500">
              Menampilkan {startIndex + 1} - {Math.min(startIndex + pageSize, sortedCandidates.length)} dari {sortedCandidates.length} data
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs px-2.5 rounded-sm"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
              >
                Sebelumnya
              </Button>
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                <Button
                  key={page}
                  variant={currentPage === page ? "default" : "outline"}
                  size="sm"
                  className={`h-7 text-xs w-7 p-0 rounded-sm ${
                    currentPage === page ? "bg-zinc-900 text-white hover:bg-zinc-800" : ""
                  }`}
                  onClick={() => setCurrentPage(page)}
                >
                  {page}
                </Button>
              ))}
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs px-2.5 rounded-sm"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
              >
                Berikutnya
              </Button>
            </div>
          </div>
        )}
      </div>
      )}'''
)

with open('src/pages/JobDetail.jsx', 'w', encoding='utf-8') as f:
    f.write(jd_content)
print("JobDetail.jsx patched.")
