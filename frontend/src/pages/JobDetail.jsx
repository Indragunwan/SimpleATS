import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api, { BAND_COLORS, RECOMMENDATION_LABELS, SCORE_BAND } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ArrowLeft, Upload, RotateCw, Briefcase, Search, Sparkles, Trash2, HelpCircle, Pencil, Save, X, Settings2, Users, ChevronUp, ChevronDown, ChevronsUpDown, AlertCircle } from "lucide-react";
import { Input } from "@/components/ui/input";
import CriteriaEditor from "@/components/CriteriaEditor";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const TABS = [
  { id: "criteria", label: "Kriteria & Bobot", icon: Settings2 },
  { id: "candidates", label: "Kandidat & Ranking", icon: Users },
];

export default function JobDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [job, setJob] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const location = useLocation();
  const [activeTab, setActiveTab] = useState(location.state?.activeTab || "criteria");
  const [sortConfig, setSortConfig] = useState({ key: "total_score", direction: "desc" });
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [reprocessingIds, setReprocessingIds] = useState(new Set());
  const [rescreenAllOpen, setRescreenAllOpen] = useState(false);
  const [rescreeningAll, setRescreeningAll] = useState(false);
  const [selectedFailedCandidate, setSelectedFailedCandidate] = useState(null);

  const formatDuration = (seconds) => {
    if (seconds < 60) return `${seconds} detik`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return secs > 0 ? `${mins} menit ${secs} detik` : `${mins} menit`;
  };

  const formatRupiah = (amount) => {
    return new Intl.NumberFormat("id-ID").format(amount);
  };

  const formatCompact = (num) => {
    if (num === null || num === undefined || isNaN(num)) return "0";
    if (num >= 1000000) {
      const val = num / 1000000;
      return parseFloat(val.toFixed(1)) + "M";
    }
    if (num >= 1000) {
      const val = num / 1000;
      return parseFloat(val.toFixed(1)) + "K";
    }
    return Number(num) % 1 === 0 ? num.toString() : parseFloat(Number(num).toFixed(2)).toString();
  };

  const handleRescreenAll = async () => {
    setRescreeningAll(true);
    try {
      await api.post(`/jobs/${id}/candidates/rescreen-all`);
      toast.success("Pemrosesan ulang massal dimulai di latar belakang");
      setRescreenAllOpen(false);
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal memproses ulang semua kandidat");
    } finally {
      setRescreeningAll(false);
    }
  };

  const handleSort = (key) => {
    let direction = "asc";
    if (sortConfig.key === key && sortConfig.direction === "asc") {
      direction = "desc";
    }
    setSortConfig({ key, direction });
    setCurrentPage(1);
  };
  const [search, setSearch] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [poolOpen, setPoolOpen] = useState(false);
  const fileInputRef = useRef(null);
  useEffect(() => {
    setCurrentPage(1);
  }, [search, minScore]);
  const pollRef = useRef(null);

  const [editingMeta, setEditingMeta] = useState(false);
  const [metaForm, setMetaForm] = useState({
    status: "",
    min_experience_years: 0,
    must_have: 40,
    experience: 30,
    domain: 15,
    education: 5,
    nice_have: 10,
    shortlist_threshold: 75,
  });

  const startEditingMeta = () => {
    setMetaForm({
      status: job.status || "draft",
      min_experience_years: job.min_experience_years || 0,
      must_have: job.weights?.must_have ?? 40,
      experience: 0,
      domain: job.weights?.domain ?? 15,
      education: job.weights?.education ?? 5,
      nice_have: job.weights?.nice_have ?? 10,
      shortlist_threshold: job.weights?.shortlist_threshold ?? 75,
    });
    setEditingMeta(true);
  };

  const saveMeta = async () => {
    const totalWeights =
      Number(metaForm.must_have) +
      Number(metaForm.domain) +
      Number(metaForm.education) +
      Number(metaForm.nice_have);

    if (totalWeights !== 100) {
      toast.error(`Total bobot harus 100% (saat ini: ${totalWeights}%)`);
      return;
    }

    try {
      const { data } = await api.patch(`/jobs/${id}`, {
        status: metaForm.status,
        min_experience_years: Number(metaForm.min_experience_years),
        weights: {
          must_have: Number(metaForm.must_have),
          experience: 0,
          domain: Number(metaForm.domain),
          education: Number(metaForm.education),
          nice_have: Number(metaForm.nice_have),
          shortlist_threshold: Number(metaForm.shortlist_threshold),
          edu_level_pct: job.weights?.edu_level_pct ?? 70,
          edu_major_pct: job.weights?.edu_major_pct ?? 30,
          reject_threshold: job.weights?.reject_threshold ?? 40,
        },
      });
      setJob(data);
      toast.success("Detail lowongan diperbarui");
      setEditingMeta(false);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal memperbarui detail lowongan");
    }
  };

  const load = useCallback(async () => {
    const [j, c] = await Promise.all([
      api.get(`/jobs/${id}`),
      api.get(`/jobs/${id}/candidates`),
    ]);
    setJob(j.data);
    setCandidates(c.data);
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while any candidate is processing
  useEffect(() => {
    const pending = candidates.some(
      (c) =>
        c.candidate_status === "pending" ||
        c.candidate_status === "processing" ||
        (c.candidate_status === "parsed" && !c.id)
    );
    if (pending) {
      pollRef.current = setTimeout(load, 4000);
    }
    return () => clearTimeout(pollRef.current);
  }, [candidates, load]);

  const handleUpload = async (files) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      const fd = new FormData();
      for (const f of files) fd.append("files", f);
      const { data } = await api.post(`/jobs/${id}/upload-cv`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`${data.uploaded} CV diunggah. Sedang diproses...`);
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal mengunggah");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleReextract = async () => {
    try {
      const { data } = await api.post(`/jobs/${id}/reextract`);
      setJob(data);
      toast.success("Kriteria di-ekstrak ulang");
    } catch (err) {
      toast.error("Gagal ekstrak ulang");
    }
  };

  const handleDeleteJob = async () => {
    if (candidates.length > 0) {
      toast.error("Hapus semua kandidat terlebih dahulu sebelum menghapus lowongan.");
      return;
    }
    if (!window.confirm("Yakin ingin menghapus lowongan ini? Tindakan ini tidak dapat dibatalkan.")) return;
    try {
      await api.delete(`/jobs/${id}`);
      toast.success("Lowongan berhasil dihapus");
      navigate("/jobs");
    } catch (err) {
      toast.error("Gagal menghapus lowongan");
    }
  };

  const handleRescreenCandidate = async (candidateId) => {
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

  const handleDeleteCandidate = async (candidateId) => {
    if (!window.confirm("Yakin ingin menghapus kandidat ini?")) return;
    try {
      await api.delete(`/jobs/${id}/candidates/${candidateId}`);
      toast.success("Kandidat berhasil dihapus");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal menghapus kandidat");
    }
  };

  if (!job) return <div className="p-10 text-zinc-500" data-testid="job-loading">Memuat...</div>;

  const filtered = candidates.filter(
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
    } else if (sortConfig.key === "total_tokens") {
      valA = a.total_tokens || 0;
      valB = b.total_tokens || 0;
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
  const totalPages = Math.ceil(sortedCandidates.length / pageSize);

  return (
    <div className="p-10" data-testid="job-detail-page">
      <button
        onClick={() => navigate("/jobs")}
        className="text-xs text-zinc-500 hover:text-zinc-900 inline-flex items-center gap-1 mb-4"
        data-testid="back-to-jobs"
      >
        <ArrowLeft size={12} /> Kembali ke Lowongan
      </button>

      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-zinc-500 uppercase tracking-wider mb-2">
            <Briefcase size={12} />
            {job.department || "—"}
          </div>
          <h1 className="font-heading text-3xl font-semibold tracking-tight" data-testid="job-title">
            {job.title}
          </h1>
          {job.target_position && (
            <p className="text-sm text-zinc-500 mt-1">Posisi target: {job.target_position}</p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setPoolOpen(true)}
            className="rounded-sm border-zinc-300"
            data-testid="suggest-from-pool-button"
          >
            <Sparkles size={14} className="mr-1.5" /> Saran dari Pool
          </Button>
          {user?.role !== "hr_recruiter" && (
              <Button
            variant="outline"
            onClick={handleReextract}
            className="rounded-sm border-zinc-300"
            data-testid="reextract-button"
          >
            <RotateCw size={14} className="mr-1.5" /> Ekstrak Ulang
          </Button>
            )}
          {user?.role !== "hr_recruiter" && (
              <Button
            variant="outline"
            onClick={handleDeleteJob}
            className="rounded-sm border-rose-200 text-rose-600 hover:bg-rose-50 hover:text-rose-700"
            data-testid="delete-job-button"
          >
            <Trash2 size={14} className="mr-1.5" /> Hapus Lowongan
          </Button>
            )}
          {activeTab === "candidates" && (
            <>
              <Button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="rounded-sm bg-zinc-900 hover:bg-zinc-800"
                data-testid="upload-cv-button"
              >
                <Upload size={14} className="mr-1.5" />
                {uploading ? "Mengunggah..." : "Unggah CV"}
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.doc,.txt"
                className="hidden"
                onChange={(e) => handleUpload(e.target.files)}
                data-testid="upload-cv-input"
              />
            </>
          )}
        </div>
      </header>

      
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
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
        <div className="lg:col-span-2">
          <CriteriaEditor job={job} onUpdate={load} editable={user?.role !== "hr_recruiter"} />
        </div>

        <div className="bg-white border border-zinc-200 rounded-sm p-5 h-fit" data-testid="job-meta">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-zinc-100">
            <h3 className="font-heading text-sm font-semibold tracking-tight text-zinc-800">
              Konfigurasi Lowongan
            </h3>
            {!editingMeta ? (
              user?.role !== "hr_recruiter" && (
                <Button
                  onClick={startEditingMeta}
                  variant="outline"
                  size="sm"
                  className="rounded-sm border-zinc-300 h-7 text-xs"
                  data-testid="edit-meta-button"
                >
                  <Pencil size={12} className="mr-1" /> Edit
                </Button>
              )
            ) : (
              <div className="flex gap-1.5">
                <Button
                  onClick={() => setEditingMeta(false)}
                  variant="outline"
                  size="sm"
                  className="rounded-sm border-zinc-300 h-7 text-xs"
                >
                  Batal
                </Button>
                <Button
                  onClick={saveMeta}
                  disabled={
                    Number(metaForm.must_have) +
                    Number(metaForm.experience) +
                    Number(metaForm.domain) +
                    Number(metaForm.education) +
                    Number(metaForm.nice_have) !== 100
                  }
                  size="sm"
                  className="rounded-sm h-7 text-xs bg-zinc-900 hover:bg-zinc-800 disabled:opacity-50"
                  data-testid="save-meta-button"
                >
                  <Save size={12} className="mr-1" /> Simpan
                </Button>
              </div>
            )}
          </div>
          {!editingMeta ? (
            <TooltipProvider>
              <div className="space-y-3 text-sm">
                <Meta label="Status" value={job.status} />
                <Meta label="Min. Pengalaman" value={`${job.min_experience_years} tahun`} />
                <MetaWithTooltip
                  label="Bobot Pengalaman"
                  value={`${job.weights?.must_have || 40}%`}
                  tooltip="Mengukur kecocokan kandidat terhadap kriteria wajib/pengalaman utama (Must-Have). Nilai kriteria wajib (bobot 1-5) akan mempengaruhi skor ini secara semantik."
                />
                <MetaWithTooltip
                  label="Bobot Wajib"
                  value={`${job.weights?.nice_have || 10}%`}
                  tooltip="Mengukur kecocokan kandidat terhadap kriteria opsional/tambahan (Nice-to-Have) yang menjadi nilai tambah."
                />
                <MetaWithTooltip
                  label="Bobot Pendidikan"
                  value={`${job.weights?.education || 5}%`}
                  tooltip="Mengukur kesesuaian jenjang pendidikan minimum (S1/S2/dll) dan jurusan kandidat. Distribusi bobot jenjang vs jurusan dapat diubah di panel Pendidikan."
                />
                <MetaWithTooltip
                  label="Bobot Domain"
                  value={`${job.weights?.domain || 15}%`}
                  tooltip="Mengukur pemahaman industri atau domain keahlian kandidat berdasarkan riwayat kerja dan deskripsi pekerjaan."
                />
                <MetaWithTooltip
                  label="Threshold Shortlist"
                  value={`≥ ${job.weights?.shortlist_threshold || 75}`}
                  tooltip="Skor total minimum (skala 0-100) yang harus dicapai oleh kandidat agar direkomendasikan masuk ke daftar pendek (Shortlist)."
                />
              </div>
            </TooltipProvider>
          ) : (
            <div className="space-y-3 text-xs">
              <div>
                <label className="text-[10px] uppercase tracking-wider text-zinc-500 font-semibold">Status</label>
                <select
                  value={metaForm.status}
                  onChange={(e) => setMetaForm({ ...metaForm, status: e.target.value })}
                  className="w-full border border-zinc-300 rounded-sm text-sm h-8 px-2 mt-1"
                  data-testid="edit-status-select"
                >
                  <option value="draft">draft</option>
                  <option value="active">active</option>
                  <option value="closed">closed</option>
                  <option value="archived">archived</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] uppercase tracking-wider text-zinc-500 font-semibold">Min. Pengalaman (Tahun)</label>
                <Input
                  type="number"
                  min="0"
                  value={metaForm.min_experience_years}
                  onChange={(e) => setMetaForm({ ...metaForm, min_experience_years: parseInt(e.target.value) || 0 })}
                  className="h-8 mt-1 rounded-sm text-sm"
                  data-testid="edit-experience-input"
                />
              </div>

              <div className="pt-2 border-t border-zinc-100">
                <div className="flex justify-between items-baseline mb-1">
                  <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-bold">Bobot Dimensi Penilaian</span>
                  <span className={`text-xs font-mono font-bold ${
                    Number(metaForm.must_have) +
                    Number(metaForm.domain) +
                    Number(metaForm.education) +
                    Number(metaForm.nice_have) === 100 ? "text-emerald-600" : "text-rose-600"
                  }`}>
                    Total: {
                      Number(metaForm.must_have) +
                      Number(metaForm.domain) +
                      Number(metaForm.education) +
                      Number(metaForm.nice_have)
                    }% / 100%
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 mt-2">
                  <div>
                    <label className="text-[9px] uppercase tracking-wider text-zinc-500">Bobot Pengalaman (%)</label>
                    <Input
                      type="number"
                      min="0"
                      max="100"
                      value={metaForm.must_have}
                      onChange={(e) => setMetaForm({ ...metaForm, must_have: parseInt(e.target.value) || 0 })}
                      className="h-8 mt-1 rounded-sm text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-[9px] uppercase tracking-wider text-zinc-500">Bobot Wajib (%)</label>
                    <Input
                      type="number"
                      min="0"
                      max="100"
                      value={metaForm.nice_have}
                      onChange={(e) => setMetaForm({ ...metaForm, nice_have: parseInt(e.target.value) || 0 })}
                      className="h-8 mt-1 rounded-sm text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-[9px] uppercase tracking-wider text-zinc-500">Bobot Pendidikan (%)</label>
                    <Input
                      type="number"
                      min="0"
                      max="100"
                      value={metaForm.education}
                      onChange={(e) => setMetaForm({ ...metaForm, education: parseInt(e.target.value) || 0 })}
                      className="h-8 mt-1 rounded-sm text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-[9px] uppercase tracking-wider text-zinc-500">Bobot Domain (%)</label>
                    <Input
                      type="number"
                      min="0"
                      max="100"
                      value={metaForm.domain}
                      onChange={(e) => setMetaForm({ ...metaForm, domain: parseInt(e.target.value) || 0 })}
                      className="h-8 mt-1 rounded-sm text-sm"
                    />
                  </div>
                </div>

                {Number(metaForm.must_have) +
                 Number(metaForm.domain) +
                 Number(metaForm.education) +
                 Number(metaForm.nice_have) !== 100 && (
                  <p className="text-[10px] text-rose-500 mt-2 italic font-medium">
                    *Jumlah keempat bobot di atas harus tepat bernilai 100% agar dapat disimpan.
                  </p>
                )}
              </div>

              <div className="pt-2 border-t border-zinc-100">
                <label className="text-[10px] uppercase tracking-wider text-zinc-500 font-semibold">Threshold Shortlist (0-100)</label>
                <Input
                  type="number"
                  min="0"
                  max="100"
                  value={metaForm.shortlist_threshold}
                  onChange={(e) => setMetaForm({ ...metaForm, shortlist_threshold: parseInt(e.target.value) || 0 })}
                  className="h-8 mt-1 rounded-sm text-sm"
                  data-testid="edit-threshold-input"
                />
              </div>
            </div>
          )}

          <div className="text-xs text-zinc-400 mt-3 pt-3 border-t border-zinc-200">
            Setelah mengedit kriteria atau konfigurasi, unggah CV baru agar bobot baru diterapkan.
          </div>
        </div>
      </div>

      
      ) : (
      <div className="bg-white border border-zinc-200 rounded-sm" data-testid="candidates-section">
        <div className="px-5 py-4 border-b border-zinc-200 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-heading text-base font-semibold tracking-tight">
              Ranking Kandidat
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              {candidates.length} total · {filtered.length} ditemukan
            </p>
          </div>
          <div className="flex items-center gap-2">
            {candidates.length > 0 && user?.role !== "hr_recruiter" && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setRescreenAllOpen(true)}
                className="rounded-sm border-zinc-300 text-zinc-700 hover:bg-zinc-50 h-8 text-xs font-semibold mr-1.5"
              >
                <RotateCw size={12} className="mr-1.5" /> Proses Ulang Semua
              </Button>
            )}
            <div className="relative">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
              <Input
                placeholder="Cari nama..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="rounded-sm h-8 text-xs pl-7 w-40"
                data-testid="candidate-search"
              />
            </div>
            <select
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
            </div>
          </div>
        </div>

        <table className="w-full text-sm">
          <thead className="bg-zinc-50/60 border-b border-zinc-200">
            <tr className="text-left">
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
              <th 
                className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide cursor-pointer hover:bg-zinc-100/80 transition-colors select-none text-center w-32"
                onClick={() => handleSort("total_tokens")}
                title="Total token yang digunakan & estimasi biaya pemrosesan AI dalam Rupiah (model Gemini 2.5 Flash, kurs $1 = Rp17.900)"
              >
                <div className="flex items-center justify-center gap-1">
                  <span>Token & Est. Rp</span>
                  {sortConfig.key === "total_tokens" ? (
                    sortConfig.direction === "asc" ? <ChevronUp size={12} /> : <ChevronDown size={12} />
                  ) : <ChevronsUpDown size={12} className="opacity-40" />}
                </div>
              </th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-right w-24">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {paginatedCandidates.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-5 py-12 text-center">
                  <div className="text-zinc-700 font-medium mb-1">Belum ada kandidat</div>
                  <div className="text-sm text-zinc-500">
                    Unggah CV (bisa banyak sekaligus) untuk melihat ranking otomatis.
                  </div>
                </td>
              </tr>
            ) : (
              paginatedCandidates.map((c, idx) => {
                const isProcessing =
                  c.candidate_status === "pending" ||
                  c.candidate_status === "processing" ||
                  (c.candidate_status === "parsed" && !c.id);
                const isFailed = c.candidate_status === "failed";
                return (
                  <tr
                    key={c.candidate_id + (c.id || "")}
                    className={`${isProcessing || isFailed ? "" : "hover:bg-zinc-50/80 cursor-pointer"}`}
                    onClick={() => c.id && navigate(`/screenings/${c.id}`)}
                    data-testid={`candidate-row-${c.candidate_id}`}
                  >
                    <td className="px-5 py-3 text-xs text-zinc-400 font-mono tabular-nums">{startIndex + idx + 1}</td>
                    <td className="px-5 py-3">
                      <div className="font-medium text-zinc-900">{c.candidate_name}</div>
                      <div className="text-xs text-zinc-500 mt-0.5">
                        {c.candidate_email || "—"}
                      </div>
                    </td>
                    <td className="px-5 py-3 text-center">
                      {isProcessing ? (
                        <span className="text-xs text-amber-700 font-medium inline-flex items-center gap-1.5 justify-center w-full animate-pulse">
                          <RotateCw size={10} className="animate-spin shrink-0" />
                          {c.candidate_status === "pending" ? (
                            "Menunggu..."
                          ) : c.candidate_status === "processing" ? (
                            "Mengekstrak..."
                          ) : (
                            "Menilai..."
                          )}
                        </span>
                      ) : isFailed ? (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedFailedCandidate(c);
                          }}
                          className="text-[10px] text-rose-700 hover:text-rose-800 bg-rose-50 hover:bg-rose-100 border border-rose-200 px-1.5 py-0.5 rounded-sm font-semibold inline-flex items-center gap-1 transition-colors"
                          title="Klik untuk detail kegagalan"
                        >
                          <AlertCircle size={10} /> Gagal
                        </button>
                      ) : (
                        <ScoreBadge score={c.total_score} />
                      )}
                    </td>
                    <td className="px-5 py-3">
                      {c.must_have && <MiniBar score={c.must_have.score} />}
                    </td>
                    <td className="px-5 py-3">
                      {c.experience && <MiniBar score={c.experience.score} />}
                    </td>
                    <td className="px-5 py-3">
                      {!isProcessing && !isFailed && (
                        <RecommendationBadge rec={c.recommendation} />
                      )}
                    </td>
                    <td className="px-5 py-3">
                      {!isProcessing && !isFailed && (
                        <DecisionBadge decision={c.decision} />
                      )}
                    </td>
                    <td className="px-5 py-3 text-center text-xs text-zinc-600 font-mono">
                      {!isProcessing && !isFailed && c.total_tokens ? (
                        (() => {
                          const USD_TO_IDR = 17900;
                          const promptCost = (c.prompt_tokens || 0) * (0.30 / 1000000);
                          const completionCost = (c.completion_tokens || 0) * (2.50 / 1000000);
                          const totalCostRp = (promptCost + completionCost) * USD_TO_IDR;
                          
                          const formattedTokens = formatCompact(c.total_tokens);
                          const formattedRp = `Rp ${formatCompact(totalCostRp)}`;
                          
                          return (
                            <div className="flex flex-col items-center justify-center">
                              <span 
                                title={`In: ${(c.prompt_tokens || 0).toLocaleString("id-ID")} | Out: ${(c.completion_tokens || 0).toLocaleString("id-ID")}`}
                                className="cursor-help border-b border-dotted border-zinc-400 font-medium text-zinc-800"
                              >
                                {formattedTokens}
                              </span>
                              <span className="text-[10px] text-zinc-500 mt-0.5">
                                {formattedRp}
                              </span>
                            </div>
                          );
                        })()
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        {c.candidate_id && (
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
                        )}
                        {c.id && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/screenings/${c.id}`);
                            }}
                            data-testid={`view-screening-${c.id}`}
                            className="text-xs px-2.5 py-1 rounded-sm border border-zinc-300 text-zinc-700 hover:bg-zinc-900 hover:text-white hover:border-zinc-900 transition-colors font-medium"
                          >
                            Detail →
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
        
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
      )}

      {poolOpen && (
        <SuggestFromPoolDialog
          jobId={id}
          onClose={() => setPoolOpen(false)}
          onQueued={() => {
            setPoolOpen(false);
            setTimeout(load, 1500);
          }}
        />
      )}

      {rescreenAllOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white border border-zinc-200 rounded-sm w-full max-w-md p-6">
            <h3 className="font-heading text-lg font-semibold tracking-tight mb-4 flex items-center gap-2">
              <RotateCw size={18} className="text-indigo-600 animate-pulse" /> Proses Ulang Semua CV
            </h3>
            <div className="space-y-3 text-sm text-zinc-600">
              <p>
                Anda akan memproses ulang <strong>{candidates.length} CV kandidat</strong> pada lowongan ini menggunakan konfigurasi bobot kriteria terbaru.
              </p>
              <div className="bg-zinc-50 border border-zinc-200 rounded-sm p-4 space-y-2 font-medium text-zinc-800">
                <div className="flex justify-between">
                  <span>Estimasi Waktu:</span>
                  <span className="text-indigo-700">~{formatDuration(candidates.length * 8)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Estimasi Biaya Token:</span>
                  <span className="text-indigo-700">Rp {formatRupiah(candidates.length * 50)}</span>
                </div>
              </div>
              <p className="text-xs text-zinc-400 italic">
                *Proses ini berjalan satu per satu di latar belakang secara otomatis. Halaman akan memperbarui status kandidat secara real-time.
              </p>
            </div>
            <div className="mt-6 flex justify-end gap-2.5">
              <Button
                variant="outline"
                className="rounded-sm border-zinc-300"
                onClick={() => setRescreenAllOpen(false)}
                disabled={rescreeningAll}
              >
                Batal
              </Button>
              <Button
                onClick={handleRescreenAll}
                disabled={rescreeningAll}
                className="rounded-sm bg-indigo-600 hover:bg-indigo-700 text-white font-medium"
              >
                {rescreeningAll ? "Memulai..." : "Ya, Proses Ulang Semua"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {selectedFailedCandidate && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-zinc-200 rounded-sm w-full max-w-md p-6 shadow-xl">
            <div className="flex items-start justify-between gap-3 mb-4">
              <h3 className="font-heading text-lg font-semibold text-rose-950 tracking-tight flex items-center gap-2">
                <AlertCircle size={20} className="text-rose-600" /> Detail Kegagalan Screening
              </h3>
              <button
                onClick={() => setSelectedFailedCandidate(null)}
                className="text-zinc-400 hover:text-zinc-600 transition-colors"
              >
                <X size={18} />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-zinc-400 font-semibold mb-1">Nama Kandidat</div>
                <div className="text-sm font-semibold text-zinc-800">{selectedFailedCandidate.candidate_name}</div>
                {selectedFailedCandidate.candidate_email && (
                  <div className="text-xs text-zinc-500 font-mono mt-0.5">{selectedFailedCandidate.candidate_email}</div>
                )}
              </div>
              
              <div>
                <div className="text-[10px] uppercase tracking-wider text-zinc-400 font-semibold mb-1">Penyebab Gagal</div>
                <div className="bg-rose-50/50 border border-rose-100 text-rose-900 rounded-sm p-4 text-xs font-mono whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
                  {selectedFailedCandidate.candidate_error || "Terjadi kesalahan internal yang tidak diketahui selama memproses CV."}
                </div>
              </div>

              <p className="text-xs text-zinc-400 italic">
                *Anda dapat mencoba memproses ulang kandidat ini menggunakan tombol 'Proses Ulang' (putar) pada baris aksi setelah memperbaiki masalah konfigurasi atau koneksi.
              </p>
            </div>
            
            <div className="mt-6 flex justify-end gap-2">
              <Button
                variant="outline"
                className="rounded-sm border-zinc-300 text-xs h-9"
                onClick={() => setSelectedFailedCandidate(null)}
              >
                Tutup
              </Button>
              {user?.role !== "hr_recruiter" && (
                <Button
                  onClick={async () => {
                    const cid = selectedFailedCandidate.candidate_id;
                    setSelectedFailedCandidate(null);
                    if (cid) {
                      await handleRescreenCandidate(cid);
                    }
                  }}
                  className="rounded-sm bg-zinc-900 hover:bg-zinc-800 text-white font-medium text-xs h-9 flex items-center gap-1.5"
                >
                  <RotateCw size={12} /> Coba Lagi
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SuggestFromPoolDialog({ jobId, onClose, onQueued }) {
  const [pool, setPool] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .get("/talent-pool")
      .then((r) => setPool(r.data))
      .finally(() => setLoading(false));
  }, []);

  const toggle = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  const submit = async () => {
    if (selected.size === 0) {
      toast.error("Pilih minimal satu kandidat");
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await api.post(`/jobs/${jobId}/screen-from-pool`, {
        candidate_ids: Array.from(selected),
      });
      toast.success(`${data.queued} kandidat di-screening ulang${data.skipped_already_screened ? ` (${data.skipped_already_screened} dilewati)` : ""}`);
      onQueued();
    } catch (err) {
      toast.error("Gagal memproses");
    } finally {
      setSubmitting(false);
    }
  };

  const autoSelectTop = (n) => {
    const ids = pool.slice(0, n).map((c) => c.id);
    setSelected(new Set(ids));
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="bg-white border border-zinc-200 rounded-sm w-full max-w-2xl max-h-[80vh] flex flex-col" data-testid="suggest-pool-dialog">
        <div className="px-6 py-4 border-b border-zinc-200">
          <h3 className="font-heading text-lg font-semibold tracking-tight">Saran dari Talent Pool</h3>
          <p className="text-xs text-zinc-500 mt-1">
            Pilih kandidat dari pool untuk di-screening terhadap JD ini (kandidat yang sudah pernah di-screening akan otomatis dilewati).
          </p>
        </div>
        <div className="px-6 py-3 border-b border-zinc-200 flex items-center justify-between gap-2 text-xs">
          <div className="text-zinc-500">{selected.size} dipilih · {pool.length} di pool</div>
          <div className="flex gap-1">
            <button
              onClick={() => autoSelectTop(5)}
              className="px-2 py-1 border border-zinc-300 rounded-sm hover:bg-zinc-50"
              data-testid="auto-top-5"
            >
              Top 5
            </button>
            <button
              onClick={() => autoSelectTop(10)}
              className="px-2 py-1 border border-zinc-300 rounded-sm hover:bg-zinc-50"
              data-testid="auto-top-10"
            >
              Top 10
            </button>
            <button
              onClick={() => setSelected(new Set())}
              className="px-2 py-1 border border-zinc-300 rounded-sm hover:bg-zinc-50"
            >
              Bersihkan
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-8 text-center text-zinc-500 text-sm">Memuat...</div>
          ) : pool.length === 0 ? (
            <div className="p-8 text-center">
              <div className="text-zinc-700 font-medium mb-1">Pool masih kosong</div>
              <div className="text-sm text-zinc-500">Belum ada kandidat ter-parsing dalam sistem.</div>
            </div>
          ) : (
            <ul className="divide-y divide-zinc-100">
              {pool.map((c) => (
                <li
                  key={c.id}
                  onClick={() => toggle(c.id)}
                  className="px-6 py-3 flex items-center gap-3 cursor-pointer hover:bg-zinc-50"
                  data-testid={`pool-pick-${c.id}`}
                >
                  <input
                    type="checkbox"
                    checked={selected.has(c.id)}
                    onChange={() => toggle(c.id)}
                    className="rounded-sm"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm">{c.name}</div>
                    <div className="text-xs text-zinc-500 mt-0.5">
                      {c.current_position || "—"} · {c.years_of_experience} thn ·{" "}
                      {c.top_skills.slice(0, 3).join(", ")}
                    </div>
                  </div>
                  {c.best_score > 0 && (
                    <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded-sm border ${BAND_COLORS[SCORE_BAND(c.best_score)]}`}>
                      {c.best_score}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="px-6 py-4 border-t border-zinc-200 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} className="rounded-sm border-zinc-300">
            Batal
          </Button>
          <Button
            onClick={submit}
            disabled={submitting || selected.size === 0}
            className="rounded-sm bg-zinc-900 hover:bg-zinc-800"
            data-testid="submit-pool-screening"
          >
            {submitting ? "Memproses..." : `Screening ${selected.size} Kandidat`}
          </Button>
        </div>
      </div>
    </div>
  );
}

function Meta({ label, value }) {
  return (
    <div className="flex justify-between items-baseline gap-3">
      <span className="text-xs text-zinc-500 uppercase tracking-wider">{label}</span>
      <span className="text-xs font-medium text-zinc-900 text-right">{value}</span>
    </div>
  );
}

function MetaWithTooltip({ label, value, tooltip }) {
  return (
    <div className="flex justify-between items-baseline gap-3">
      <Tooltip>
        <TooltipTrigger asChild>
          <button className="text-xs text-zinc-500 hover:text-zinc-900 font-normal uppercase tracking-wider inline-flex items-center gap-1 text-left decoration-dotted underline underline-offset-2 cursor-help">
            {label}
            <HelpCircle size={10} className="text-zinc-400 shrink-0" />
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-[240px] text-left bg-zinc-900 text-white rounded p-2 text-xs shadow-md">
          <p>{tooltip}</p>
        </TooltipContent>
      </Tooltip>
      <span className="text-xs font-medium text-zinc-900 text-right">{value}</span>
    </div>
  );
}

export function ScoreBadge({ score }) {
  const band = SCORE_BAND(score);
  return (
    <span
      className={`inline-block min-w-[52px] text-center font-mono tabular-nums font-semibold text-sm px-2 py-1 rounded-sm border ${BAND_COLORS[band]}`}
      data-testid="score-badge"
    >
      {score}
    </span>
  );
}

function MiniBar({ score }) {
  const band = SCORE_BAND(score || 0);
  const barColor = { high: "bg-emerald-500", mid: "bg-amber-500", low: "bg-rose-500" }[band];
  return (
    <div className="flex items-center gap-2 w-24">
      <div className="flex-1 h-1 bg-zinc-100 rounded-sm overflow-hidden">
        <div className={`h-full ${barColor}`} style={{ width: `${score || 0}%` }} />
      </div>
      <span className="text-xs font-mono tabular-nums text-zinc-600 w-6">{score || 0}</span>
    </div>
  );
}

function RecommendationBadge({ rec }) {
  const cls =
    rec === "shortlist"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : rec === "reject"
      ? "bg-rose-50 text-rose-700 border-rose-200"
      : "bg-amber-50 text-amber-700 border-amber-200";
  return (
    <span className={`text-xs px-2 py-0.5 rounded-sm border font-medium ${cls}`}>
      {RECOMMENDATION_LABELS[rec] || rec}
    </span>
  );
}

function DecisionBadge({ decision }) {
  if (decision === "pending" || !decision) {
    return <span className="text-xs text-zinc-400">—</span>;
  }
  const cls =
    decision === "shortlisted"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : decision === "rejected"
      ? "bg-rose-50 text-rose-700 border-rose-200"
      : "bg-zinc-50 text-zinc-700 border-zinc-200";
  const labels = {
    shortlisted: "Shortlist",
    rejected: "Tolak",
    hold: "Tahan",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-sm border font-medium ${cls}`}>
      {labels[decision] || decision}
    </span>
  );
}
