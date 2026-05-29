import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { BAND_COLORS, RECOMMENDATION_LABELS, SCORE_BAND } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ArrowLeft, Upload, RotateCw, Briefcase, Search, Sparkles, Trash2, HelpCircle, Pencil, Save, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import CriteriaEditor from "@/components/CriteriaEditor";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export default function JobDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [search, setSearch] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [poolOpen, setPoolOpen] = useState(false);
  const fileInputRef = useRef(null);
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

  const handleDeleteCandidate = async (candidateId) => {
    if (!window.confirm("Yakin ingin menghapus kandidat ini?")) return;
    try {
      await api.delete(`/jobs/${id}/candidates/${candidateId}`);
      toast.success("Kandidat berhasil dihapus");
      setLoad((l) => l + 1);
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
          <Button
            variant="outline"
            onClick={handleReextract}
            className="rounded-sm border-zinc-300"
            data-testid="reextract-button"
          >
            <RotateCw size={14} className="mr-1.5" /> Ekstrak Ulang
          </Button>
          <Button
            variant="outline"
            onClick={handleDeleteJob}
            className="rounded-sm border-rose-200 text-rose-600 hover:bg-rose-50 hover:text-rose-700"
            data-testid="delete-job-button"
          >
            <Trash2 size={14} className="mr-1.5" /> Hapus Lowongan
          </Button>
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
        </div>
      </header>

      {/* Criteria & Education Editor */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
        <div className="lg:col-span-2">
          <CriteriaEditor job={job} onUpdate={load} />
        </div>

        <div className="bg-white border border-zinc-200 rounded-sm p-5 h-fit" data-testid="job-meta">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-zinc-100">
            <h3 className="font-heading text-sm font-semibold tracking-tight text-zinc-800">
              Konfigurasi Lowongan
            </h3>
            {!editingMeta ? (
              <Button
                onClick={startEditingMeta}
                variant="outline"
                size="sm"
                className="rounded-sm border-zinc-300 h-7 text-xs"
                data-testid="edit-meta-button"
              >
                <Pencil size={12} className="mr-1" /> Edit
              </Button>
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

      {/* Candidates */}
      <div className="bg-white border border-zinc-200 rounded-sm" data-testid="candidates-section">
        <div className="px-5 py-4 border-b border-zinc-200 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-heading text-base font-semibold tracking-tight">
              Ranking Kandidat
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              {candidates.length} total · {filtered.length} ditampilkan
            </p>
          </div>
          <div className="flex items-center gap-2">
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
          </div>
        </div>

        <table className="w-full text-sm">
          <thead className="bg-zinc-50/60 border-b border-zinc-200">
            <tr className="text-left">
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide w-10">#</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Kandidat</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-center">Skor</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Must</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Pengalaman</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Rekomendasi</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Keputusan</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-right">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-5 py-12 text-center">
                  <div className="text-zinc-700 font-medium mb-1">Belum ada kandidat</div>
                  <div className="text-sm text-zinc-500">
                    Unggah CV (bisa banyak sekaligus) untuk melihat ranking otomatis.
                  </div>
                </td>
              </tr>
            ) : (
              filtered.map((c, idx) => {
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
                    <td className="px-5 py-3 text-xs text-zinc-400 font-mono tabular-nums">{idx + 1}</td>
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
                        <span className="text-xs text-rose-700 font-medium">Gagal</span>
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
                    <td className="px-5 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        {c.candidate_id && (
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
      </div>

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
