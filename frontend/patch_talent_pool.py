with open('frontend/src/pages/TalentPool.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# Add toast import
if 'import { toast }' not in text:
    text = text.replace(
        'import api, { BAND_COLORS, SCORE_BAND } from "@/lib/api";',
        'import api, { BAND_COLORS, SCORE_BAND } from "@/lib/api";\nimport { toast } from "sonner";'
    )

# Add searchMode and semanticQuery states
old_states = """  const [pool, setPool] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const navigate = useNavigate();"""

new_states = """  const [pool, setPool] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [searchMode, setSearchMode] = useState("keyword"); // keyword | semantic
  const [semanticQuery, setSemanticQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const navigate = useNavigate();"""

text = text.replace(old_states, new_states)

# Replace useEffect with loadPool function
old_effect = """  useEffect(() => {
    api
      .get("/talent-pool")
      .then((r) => setPool(r.data))
      .finally(() => setLoading(false));
  }, []);"""

new_effect = """  const loadPool = () => {
    setLoading(true);
    api
      .get("/talent-pool")
      .then((r) => setPool(r.data))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadPool();
  }, []);

  const handleSemanticSearch = async (e) => {
    if (e) e.preventDefault();
    if (!semanticQuery.trim()) return;
    setSearching(true);
    setLoading(true);
    try {
      const { data } = await api.post("/talent-pool/search", { query: semanticQuery });
      setPool(data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal melakukan pencarian semantik");
    } finally {
      setSearching(false);
      setLoading(false);
    }
  };"""

text = text.replace(old_effect, new_effect)

# Update display logic
text = text.replace(
    'const filtered = pool.filter(',
    '''const filtered = pool.filter('''
)

text = text.replace(
    '''  const stats = {
    total: pool.length,''',
    '''  const displayPool = searchMode === "keyword" ? filtered : pool;

  const stats = {
    total: pool.length,'''
)

# Replace the search bar div
old_search_bar = """        <div className="px-5 py-4 border-b border-zinc-200 flex items-center justify-between gap-3">
          <div className="text-xs text-zinc-500">{filtered.length} ditampilkan</div>
          <div className="relative w-72">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
            <Input
              placeholder="Cari nama, email, atau skill..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="rounded-sm h-8 text-xs pl-7"
              data-testid="pool-search"
            />
          </div>
        </div>"""

new_search_bar = """        <div className="px-5 py-4 border-b border-zinc-200 flex flex-wrap items-center justify-between gap-3 bg-zinc-50/40">
          <div className="flex items-center gap-4">
            <div className="flex gap-1.5">
              <button
                type="button"
                onClick={() => {
                  setSearchMode("keyword");
                  loadPool();
                }}
                className={`text-xs px-3 py-1.5 rounded-sm font-medium transition-all ${
                  searchMode === "keyword"
                    ? "bg-zinc-900 text-white"
                    : "bg-white border border-zinc-200 text-zinc-600 hover:text-zinc-900"
                }`}
              >
                Pencarian Kata Kunci
              </button>
              <button
                type="button"
                onClick={() => setSearchMode("semantic")}
                className={`text-xs px-3 py-1.5 rounded-sm font-medium transition-all inline-flex items-center gap-1 ${
                  searchMode === "semantic"
                    ? "bg-zinc-900 text-white"
                    : "bg-white border border-zinc-200 text-zinc-600 hover:text-zinc-900"
                }`}
              >
                Pencarian Semantik (AI) ✨
              </button>
            </div>
            <div className="text-xs text-zinc-500">{displayPool.length} ditampilkan</div>
          </div>

          {searchMode === "keyword" ? (
            <div className="relative w-72">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
              <Input
                placeholder="Cari nama, email, atau skill..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="rounded-sm h-8 text-xs pl-7"
                data-testid="pool-search"
              />
            </div>
          ) : (
            <form onSubmit={handleSemanticSearch} className="flex gap-2 w-full md:w-auto md:flex-1 md:justify-end max-w-md">
              <Input
                placeholder="Cari dgn AI: Lulusan S1 Ekonomi, autocad..."
                value={semanticQuery}
                onChange={(e) => setSemanticQuery(e.target.value)}
                className="rounded-sm h-8 text-xs flex-1"
                disabled={searching}
              />
              <button
                type="submit"
                disabled={searching || !semanticQuery.trim()}
                className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 h-8 rounded-sm font-medium disabled:opacity-50 transition-colors shrink-0"
              >
                {searching ? "Mencari..." : "Cari"}
              </button>
            </form>
          )}
        </div>"""

text = text.replace(old_search_bar, new_search_bar)

# Replace table headers
old_table_headers = """            <tr className="text-left">
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Kandidat</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Posisi Terakhir</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Keahlian</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-center">Exp</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-center">Skor Terbaik</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-center">Screenings</th>
            </tr>"""

new_table_headers = """            <tr className="text-left">
              {searchMode === "semantic" && (
                <th className="px-5 py-2.5 text-xs font-semibold text-indigo-700 bg-indigo-50/40 uppercase tracking-wide text-center w-28">Kecocokan AI</th>
              )}
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Kandidat</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Posisi Terakhir</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Keahlian</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-center">Exp</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-center">Skor Terbaik</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-center">Screenings</th>
            </tr>"""

text = text.replace(old_table_headers, new_table_headers)

# Replace table loading and empty spans count
text = text.replace(
    '<tr><td colSpan={6}',
    '<tr><td colSpan={searchMode === "semantic" ? 7 : 6}'
)
text = text.replace(
    '<td colSpan={6} className="px-5 py-16 text-center">',
    '<td colSpan={searchMode === "semantic" ? 7 : 6} className="px-5 py-16 text-center">'
)

# Update map list source
text = text.replace(
    'filtered.map((c) => (',
    'displayPool.map((c) => ('
)

# Update list columns to include similarity score cell
old_row_start = """              filtered.map((c) => (
                <tr
                  key={c.id}
                  className="hover:bg-zinc-50/80 cursor-pointer"
                  onClick={() => navigate(`/talent-pool/${c.id}`)}
                  data-testid={`pool-row-${c.id}`}
                >
                  <td className="px-5 py-3">"""

new_row_start = """              displayPool.map((c) => (
                <tr
                  key={c.id}
                  className="hover:bg-zinc-50/80 cursor-pointer"
                  onClick={() => navigate(`/talent-pool/${c.id}`)}
                  data-testid={`pool-row-${c.id}`}
                >
                  {searchMode === "semantic" && (
                    <td className="px-5 py-3 text-center bg-indigo-50/20">
                      <span className="inline-block text-xs font-bold font-mono text-indigo-700 bg-indigo-50 px-2.5 py-0.5 border border-indigo-200 rounded-sm">
                        {c.similarity_score}%
                      </span>
                    </td>
                  )}
                  <td className="px-5 py-3">"""

# Let's apply row mapping replace
text = text.replace(
    '''            ) : (
              filtered.map((c) => (
                <tr
                  key={c.id}
                  className="hover:bg-zinc-50/80 cursor-pointer"
                  onClick={() => navigate(`/talent-pool/${c.id}`)}
                  data-testid={`pool-row-${c.id}`}
                >
                  <td className="px-5 py-3">''',
    '''            ) : (
              displayPool.map((c) => (
                <tr
                  key={c.id}
                  className="hover:bg-zinc-50/80 cursor-pointer"
                  onClick={() => navigate(`/talent-pool/${c.id}`)}
                  data-testid={`pool-row-${c.id}`}
                >
                  {searchMode === "semantic" && (
                    <td className="px-5 py-3 text-center bg-indigo-50/20">
                      <span className="inline-block text-xs font-bold font-mono text-indigo-700 bg-indigo-50 px-2.5 py-0.5 border border-indigo-200 rounded-sm">
                        {c.similarity_score}%
                      </span>
                    </td>
                  )}
                  <td className="px-5 py-3">'''
)

with open('frontend/src/pages/TalentPool.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("TalentPool.jsx patched.")
