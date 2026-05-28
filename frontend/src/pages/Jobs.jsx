import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
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
import { Plus, FileText, Users } from "lucide-react";

export default function Jobs() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

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
        <CreateJobDialog open={open} setOpen={setOpen} onCreated={load} />
      </header>

      <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden" data-testid="jobs-table-wrapper">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 border-b border-zinc-200">
            <tr className="text-left">
              <th className="px-5 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wide">Posisi</th>
              <th className="px-5 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wide">Departemen</th>
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
                  </td>
                  <td className="px-5 py-4 text-zinc-600">{j.department || "—"}</td>
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
                    <span className="text-xs text-zinc-400">→</span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

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

function CreateJobDialog({ open, setOpen, onCreated }) {
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("");
  const [rawJd, setRawJd] = useState("");
  const [file, setFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim()) {
      toast.error("Judul harus diisi");
      return;
    }
    if (!rawJd.trim() && !file) {
      toast.error("Teks JD atau file harus disediakan");
      return;
    }
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("title", title);
      fd.append("department", department);
      fd.append("raw_jd_text", rawJd);
      if (file) fd.append("file", file);

      const { data } = await api.post("/jobs", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Lowongan dibuat. Ekstraksi kriteria selesai.");
      setOpen(false);
      setTitle("");
      setDepartment("");
      setRawJd("");
      setFile(null);
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
            <Label className="text-xs uppercase tracking-wider text-zinc-600">Judul</Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Contoh: Payroll Specialist"
              data-testid="create-job-title"
              className="mt-1 rounded-sm"
            />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-600">Departemen</Label>
            <Input
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              placeholder="Contoh: People & Culture"
              data-testid="create-job-department"
              className="mt-1 rounded-sm"
            />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-600">Teks JD</Label>
            <Textarea
              value={rawJd}
              onChange={(e) => setRawJd(e.target.value)}
              placeholder="Paste deskripsi pekerjaan di sini..."
              rows={6}
              data-testid="create-job-text"
              className="mt-1 rounded-sm font-mono text-xs"
            />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-600">
              Atau Unggah File (PDF/DOCX/TXT)
            </Label>
            <input
              type="file"
              accept=".pdf,.docx,.doc,.txt"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              data-testid="create-job-file"
              className="mt-1 block w-full text-sm text-zinc-700 file:mr-3 file:py-2 file:px-3 file:rounded-sm file:border file:border-zinc-200 file:text-xs file:font-medium file:bg-white file:text-zinc-900 hover:file:bg-zinc-50"
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
