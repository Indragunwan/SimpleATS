import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { BAND_COLORS, RECOMMENDATION_LABELS, SCORE_BAND } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ArrowLeft, Upload, RotateCw, Briefcase, Search } from "lucide-react";
import { Input } from "@/components/ui/input";

export default function JobDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [search, setSearch] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);

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
      (c) => c.candidate_status === "pending" || c.candidate_status === "processing"
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

  if (!job) return <div className="p-10 text-zinc-500" data-testid="job-loading">Memuat...</div>;

  const filtered = candidates.filter(
    (c) =>
      (c.total_score || 0) >= minScore &&
      (search === "" ||
        (c.candidate_name || "").toLowerCase().includes(search.toLowerCase()))
  );
  const mustCriteria = (job.criteria || []).filter((c) => c.type === "must");
  const niceCriteria = (job.criteria || []).filter((c) => c.type === "nice");

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
            onClick={handleReextract}
            className="rounded-sm border-zinc-300"
            data-testid="reextract-button"
          >
            <RotateCw size={14} className="mr-1.5" /> Ekstrak Ulang
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

      {/* Criteria */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
        <div className="bg-white border border-zinc-200 rounded-sm p-5 lg:col-span-2" data-testid="job-criteria">
          <div className="text-xs uppercase tracking-wider text-zinc-500 mb-3">
            Kriteria Wajib · Must-Have
          </div>
          <div className="flex flex-wrap gap-2 mb-5">
            {mustCriteria.length === 0 ? (
              <div className="text-sm text-zinc-400">Tidak ada kriteria wajib</div>
            ) : (
              mustCriteria.map((c, i) => (
                <span
                  key={i}
                  className="text-xs px-2.5 py-1 rounded-sm border bg-emerald-50 text-emerald-700 border-emerald-200"
                  data-testid={`must-criterion-${i}`}
                >
                  {c.value}
                </span>
              ))
            )}
          </div>
          <div className="text-xs uppercase tracking-wider text-zinc-500 mb-3">
            Kriteria Tambahan · Nice-to-Have
          </div>
          <div className="flex flex-wrap gap-2">
            {niceCriteria.length === 0 ? (
              <div className="text-sm text-zinc-400">Tidak ada kriteria tambahan</div>
            ) : (
              niceCriteria.map((c, i) => (
                <span
                  key={i}
                  className="text-xs px-2.5 py-1 rounded-sm border bg-zinc-50 text-zinc-700 border-zinc-200"
                  data-testid={`nice-criterion-${i}`}
                >
                  {c.value}
                </span>
              ))
            )}
          </div>
        </div>

        <div className="bg-white border border-zinc-200 rounded-sm p-5" data-testid="job-meta">
          <div className="space-y-3 text-sm">
            <Meta label="Min. Pengalaman" value={`${job.min_experience_years} tahun`} />
            <Meta label="Pendidikan" value={job.education_requirement || "—"} />
            <Meta label="Status" value={job.status} />
            <Meta label="Bobot Must" value={`${job.weights?.must_have || 40}%`} />
            <Meta label="Bobot Pengalaman" value={`${job.weights?.experience || 30}%`} />
            <Meta label="Threshold Shortlist" value={`≥ ${job.weights?.shortlist_threshold || 75}`} />
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
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-5 py-12 text-center">
                  <div className="text-zinc-700 font-medium mb-1">Belum ada kandidat</div>
                  <div className="text-sm text-zinc-500">
                    Unggah CV (bisa banyak sekaligus) untuk melihat ranking otomatis.
                  </div>
                </td>
              </tr>
            ) : (
              filtered.map((c, idx) => {
                const isProcessing =
                  c.candidate_status === "pending" || c.candidate_status === "processing";
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
                        <span className="text-xs text-amber-700 font-medium">Memproses...</span>
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
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
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
