import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, FileText, Users, Trash2, Pencil, Lock } from "lucide-react";

export default function Jobs() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editingJob, setEditingJob] = useState(null); // job object to edit
  const navigate = useNavigate();
  const { user } = useAuth();

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/jobs");
      setJobs(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="p-10" data-testid="jobs-page">
      <header className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="font-heading text-3xl font-semibold tracking-tight">Lowongan</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Kelola Job Description dan lihat ranking kandidat per posisi.
          </p>
        </div>
        {user?.role !== "hr_recruiter" && (
          <CreateJobDialog open={open} setOpen={setOpen} onCreated={load} />
        )}
      </header>

      <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden" data-testid="jobs-table-wrapper">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 border-b border-zinc-200">
            <tr className="text-left">
              <th className="px-5 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wide">Posisi</th>
              <th className="px-5 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wide">Kriteria</th>
              <th className="px-5 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wide text-right">Kandidat</th>
              <th className="px-5 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wide">Status</th>
              <th className="px-5 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-5 py-12 text-center text-zinc-500">
                  Memuat...
                </td>
              </tr>
            ) : jobs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-16 text-center">
                  <FileText className="mx-auto text-zinc-300 mb-3" size={32} />
                  <div className="text-zinc-700 font-medium mb-1">Belum ada lowongan</div>
                  <div className="text-sm text-zinc-500 mb-4">
                    Unggah Job Description pertama untuk memulai.
                  </div>
                  <Button
                    onClick={() => setOpen(true)}
                    className="rounded-sm bg-zinc-900 hover:bg-zinc-800"
                    data-testid="create-job-empty-cta"
                  >
                    <Plus size={14} className="mr-1" /> Buat Lowongan
                  </Button>
                </td>
              </tr>
            ) : (
              jobs.map((j) => (
                <tr
                  key={j.id}
                  className="hover:bg-zinc-50/80 cursor-pointer"
                  onClick={() => navigate(`/jobs/${j.id}`)}
                  data-testid={`job-row-${j.id}`}
                >
                  <td className="px-5 py-4">
                    <div className="font-medium text-zinc-900">{j.title}</div>
                    {j.target_position && j.target_position !== j.title && (
                      <div className="text-xs text-zinc-500 mt-0.5">{j.target_position}</div>
                    )}
                    <div className="flex items-center gap-2.5 text-[10px] text-zinc-400 mt-1.5 flex-wrap">
                      {j.location && (
                        <span className="bg-zinc-100 text-zinc-700 px-1.5 py-0.5 rounded-sm font-semibold">📍 {j.location}</span>
                      )}
                      {(j.start_date || j.end_date) && (
                        <span className="bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded-sm font-semibold">📅 {j.start_date || "—"} s/d {j.end_date || "—"}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex gap-3 text-xs">
                      <span className="text-emerald-700">
                        {(j.criteria || []).filter((c) => c.type === "must").length} wajib
                      </span>
                      <span className="text-zinc-500">
                        {(j.criteria || []).filter((c) => c.type === "nice").length} tambahan
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-4 text-right tabular-nums">
                    <span className="inline-flex items-center gap-1 text-zinc-700">
                      <Users size={12} />
                      {j.candidate_count || 0}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <StatusBadge status={j.status} extraction={j.extraction_status} />
                  </td>
                  <td className="px-5 py-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      {/* Edit button — hidden for hr_recruiter */}
                      {user?.role !== "hr_recruiter" && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingJob(j);
                          }}
                          className="text-zinc-400 hover:text-zinc-700 p-1 transition-colors"
                          title="Edit Lowongan"
                          data-testid={`edit-job-${j.id}`}
                        >
                          <Pencil size={15} />
                        </button>
                      )}
                      {/* Delete button — hidden for closed jobs and hr_recruiter */}
                      {j.status !== "closed" && user?.role !== "hr_recruiter" && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (window.confirm("Yakin ingin menghapus lowongan ini?")) {
                              api.delete(`/jobs/${j.id}`).then(() => {
                                toast.success("Lowongan berhasil dihapus");
                                load();
                              }).catch((err) => {
                                toast.error(err?.response?.data?.detail || "Gagal menghapus lowongan");
                              });
                            }
                          }}
                          className="text-zinc-400 hover:text-rose-600 p-1 transition-colors"
                          title="Hapus Lowongan"
                        >
                          <Trash2 size={15} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Edit Job Dialog */}
      {editingJob && (
        <EditJobDialog
          job={editingJob}
          onClose={() => setEditingJob(null)}
          onSaved={() => { setEditingJob(null); load(); }}
        />
      )}
    </div>
  );
}

// ─── Status Badge ─────────────────────────────────────────────────────────────
function StatusBadge({ status, extraction }) {
  if (extraction === "processing") {
    return (
      <span className="text-xs px-2 py-1 rounded-sm border bg-amber-50 text-amber-700 border-amber-200 font-medium">
        Mengekstrak...
      </span>
    );
  }
  if (extraction === "failed") {
    return (
      <span className="text-xs px-2 py-1 rounded-sm border bg-rose-50 text-rose-700 border-rose-200 font-medium">
        Ekstraksi gagal
      </span>
    );
  }
  const cls =
    status === "active"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : status === "draft"
      ? "bg-zinc-50 text-zinc-600 border-zinc-200"
      : "bg-zinc-100 text-zinc-500 border-zinc-200";
  return <span className={`text-xs px-2 py-1 rounded-sm border font-medium ${cls}`}>{status}</span>;
}

// ─── Create Job Dialog ────────────────────────────────────────────────────────
function CreateJobDialog({ open, setOpen, onCreated }) {
  const [title, setTitle] = useState("");
  const [targetPosition, setTargetPosition] = useState("");
  const [rawJd, setRawJd] = useState("");
  const [rawSpec, setRawSpec] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [location, setLocation] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim()) {
      toast.error("Judul harus diisi");
      return;
    }
    if (!rawJd.trim() && !rawSpec.trim()) {
      toast.error("Teks JD atau Spesifikasi harus disediakan");
      return;
    }
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("title", title);
      fd.append("target_position", targetPosition);
      fd.append("raw_jd_text", rawJd);
      fd.append("raw_spec_text", rawSpec);
      if (startDate) fd.append("start_date", startDate);
      if (endDate) fd.append("end_date", endDate);
      if (location) fd.append("location", location);

      await api.post("/jobs", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Lowongan dibuat. Ekstraksi kriteria selesai.");
      setOpen(false);
      setTitle("");
      setTargetPosition("");
      setRawJd("");
      setRawSpec("");
      setStartDate("");
      setEndDate("");
      setLocation("");
      onCreated();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal membuat lowongan");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="rounded-sm bg-zinc-900 hover:bg-zinc-800" data-testid="create-job-button">
          <Plus size={14} className="mr-1" /> Buat Lowongan
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-sm sm:max-w-lg" data-testid="create-job-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">Buat Lowongan Baru</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-600">Judul Posisi</Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Contoh: Payroll Specialist"
              data-testid="create-job-title"
              className="mt-1 rounded-sm"
            />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-600">
              Tanggung Jawab Utama
              <span className="ml-1 normal-case text-zinc-400 font-normal">(opsional)</span>
            </Label>
            <Input
              value={targetPosition}
              onChange={(e) => setTargetPosition(e.target.value)}
              placeholder="Contoh: Mengelola proses penggajian bulanan..."
              data-testid="create-job-target-position"
              className="mt-1 rounded-sm"
            />
            <p className="text-[10px] text-zinc-400 mt-1">
              Akan tampil di bawah judul pada halaman detail lowongan. Jika dikosongkan, akan diisi otomatis dari JD.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-600">
                Lokasi Penempatan
                <span className="ml-1 normal-case text-zinc-400 font-normal">(opsional)</span>
              </Label>
              <Input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Kota atau Nama Unit"
                className="mt-1 rounded-sm text-xs"
              />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-600">
                Periode Lowongan Aktif
                <span className="ml-1 normal-case text-zinc-400 font-normal">(opsional)</span>
              </Label>
              <div className="flex gap-1.5 items-center mt-1">
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="flex h-9 w-full rounded-sm border border-zinc-200 bg-transparent px-2.5 py-1 text-xs transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950"
                />
                <span className="text-xs text-zinc-400 font-mono">s/d</span>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="flex h-9 w-full rounded-sm border border-zinc-200 bg-transparent px-2.5 py-1 text-xs transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950"
                />
              </div>
            </div>
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-600">Teks JD / Tanggung Jawab</Label>
            <Textarea
              value={rawJd}
              onChange={(e) => setRawJd(e.target.value)}
              placeholder="Paste deskripsi pekerjaan / tanggung jawab di sini..."
              rows={5}
              data-testid="create-job-jd"
              className="mt-1 rounded-sm font-mono text-xs"
            />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-600">Teks Spesifikasi / Kualifikasi</Label>
            <Textarea
              value={rawSpec}
              onChange={(e) => setRawSpec(e.target.value)}
              placeholder="Paste kualifikasi / persyaratan di sini..."
              rows={5}
              data-testid="create-job-spec"
              className="mt-1 rounded-sm font-mono text-xs"
            />
          </div>
          <DialogFooter>
            <Button
              type="submit"
              disabled={submitting}
              className="rounded-sm bg-zinc-900 hover:bg-zinc-800"
              data-testid="create-job-submit"
            >
              {submitting ? "Memproses..." : "Buat & Ekstrak Kriteria"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ─── Edit Job Dialog ──────────────────────────────────────────────────────────
function EditJobDialog({ job, onClose, onSaved }) {
  const [title, setTitle] = useState(job.title || "");
  const [targetPosition, setTargetPosition] = useState(job.target_position || "");
  const [location, setLocation] = useState(job.location || "");
  const [startDate, setStartDate] = useState(job.start_date || "");
  const [endDate, setEndDate] = useState(job.end_date || "");
  const [status, setStatus] = useState(job.status || "active");
  const [submitting, setSubmitting] = useState(false);

  const handleSave = async (e) => {
    e.preventDefault();
    if (!title.trim()) {
      toast.error("Judul harus diisi");
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        title: title.trim(),
        target_position: targetPosition.trim() || null,
        location: location.trim() || null,
        start_date: startDate || null,
        end_date: endDate || null,
        status,
      };
      await api.patch(`/jobs/${job.id}`, payload);
      toast.success("Lowongan berhasil diperbarui");
      onSaved();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal memperbarui lowongan");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="rounded-sm sm:max-w-lg" data-testid="edit-job-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">Edit Lowongan</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSave} className="space-y-4">
          {/* Judul */}
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-600">Judul Posisi</Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Contoh: Payroll Specialist"
              className="mt-1 rounded-sm"
              data-testid="edit-job-title"
            />
          </div>

          {/* Target Posisi */}
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-600">
              Deskripsi Singkat / Target Posisi
              <span className="ml-1 normal-case text-zinc-400 font-normal">(opsional)</span>
            </Label>
            <Input
              value={targetPosition}
              onChange={(e) => setTargetPosition(e.target.value)}
              placeholder="Contoh: Mengelola proses penggajian bulanan..."
              className="mt-1 rounded-sm"
              data-testid="edit-job-target-position"
            />
          </div>

          {/* Lokasi + Periode */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-600">
                Lokasi Penempatan
                <span className="ml-1 normal-case text-zinc-400 font-normal">(opsional)</span>
              </Label>
              <Input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Kota atau Nama Unit"
                className="mt-1 rounded-sm text-xs"
                data-testid="edit-job-location"
              />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-600">
                Status Lowongan
              </Label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="mt-1 flex h-9 w-full rounded-sm border border-zinc-200 bg-transparent px-2.5 py-1 text-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950"
                data-testid="edit-job-status"
              >
                <option value="draft">Draft</option>
                <option value="active">Aktif</option>
                <option value="closed">Ditutup</option>
                <option value="archived">Diarsipkan</option>
              </select>
            </div>
          </div>

          {/* Periode Aktif */}
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-600">
              Periode Lowongan Aktif
              <span className="ml-1 normal-case text-zinc-400 font-normal">(opsional)</span>
            </Label>
            <div className="flex gap-2 items-center mt-1">
              <div className="flex-1">
                <p className="text-[10px] text-zinc-400 mb-1">Mulai</p>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="flex h-9 w-full rounded-sm border border-zinc-200 bg-transparent px-2.5 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950"
                  data-testid="edit-job-start-date"
                />
              </div>
              <span className="text-xs text-zinc-400 font-mono mt-4">s/d</span>
              <div className="flex-1">
                <p className="text-[10px] text-zinc-400 mb-1">Selesai</p>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="flex h-9 w-full rounded-sm border border-zinc-200 bg-transparent px-2.5 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950"
                  data-testid="edit-job-end-date"
                />
              </div>
              {endDate && (
                <button
                  type="button"
                  onClick={() => setEndDate("")}
                  className="text-[10px] text-zinc-400 hover:text-rose-500 mt-4 whitespace-nowrap"
                >
                  Hapus
                </button>
              )}
            </div>
            {endDate && (
              <p className="text-[10px] text-amber-600 mt-1.5">
                ⚠ Jika tanggal selesai telah lewat, lowongan akan otomatis berstatus Ditutup.
              </p>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="rounded-sm border-zinc-300 text-xs"
            >
              Batal
            </Button>
            <Button
              type="submit"
              disabled={submitting}
              className="rounded-sm bg-zinc-900 hover:bg-zinc-800"
              data-testid="edit-job-submit"
            >
              {submitting ? "Menyimpan..." : "Simpan Perubahan"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
