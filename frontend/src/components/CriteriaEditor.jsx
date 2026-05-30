import { useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, GraduationCap, Save, X } from "lucide-react";

const CATEGORIES = [
  { value: "skill", label: "Keahlian" },
  { value: "experience", label: "Pengalaman" },
  { value: "certification", label: "Sertifikasi" },
  { value: "language", label: "Bahasa" },
  { value: "responsibility", label: "Tanggung Jawab" },
  { value: "gender", label: "Gender" },
  { value: "city", label: "Kota Tinggal" },
  { value: "custom", label: "Lainnya" },
];

const WEIGHT_LABELS = { 1: "Ringan", 2: "Pelengkap", 3: "Normal", 4: "Penting", 5: "Krusial" };

const EDU_LEVELS = ["SMA/SMK", "D3", "D4", "S1", "S2", "S3"];

export default function CriteriaEditor({ job, onUpdate }) {
  const [adding, setAdding] = useState(null); // 'must' | 'nice' | null
  const [editingId, setEditingId] = useState(null);

  const must = (job.criteria || []).filter((c) => c.type === "must");
  const nice = (job.criteria || []).filter((c) => c.type === "nice");

  const add = async (data) => {
    try {
      await api.post(`/jobs/${job.id}/criteria`, data);
      toast.success("Kriteria ditambahkan");
      setAdding(null);
      onUpdate();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal menambah");
    }
  };

  const update = async (cid, data) => {
    try {
      await api.patch(`/jobs/${job.id}/criteria/${cid}`, data);
      toast.success("Kriteria diperbarui");
      setEditingId(null);
      onUpdate();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal memperbarui");
    }
  };

  const remove = async (cid) => {
    if (!window.confirm("Hapus kriteria ini?")) return;
    try {
      await api.delete(`/jobs/${job.id}/criteria/${cid}`);
      toast.success("Kriteria dihapus");
      onUpdate();
    } catch (err) {
      toast.error("Gagal menghapus");
    }
  };

  const isClosed = job?.status === "closed";

  return (
    <div className="space-y-4" data-testid="criteria-editor">
      {/* Must-Have group */}
      <Group
        title="Kriteria Wajib · Must-Have"
        color="emerald"
        items={must}
        onAdd={() => setAdding("must")}
        renderItem={(c) =>
          editingId === c.id ? (
            <CriterionForm
              initial={c}
              onCancel={() => setEditingId(null)}
              onSubmit={(data) => update(c.id, data)}
            />
          ) : (
            <Row
              c={c}
              colorBand="emerald"
              onEdit={() => setEditingId(c.id)}
              onDelete={() => remove(c.id)}
              isClosed={isClosed}
            />
          )
        }
        adding={adding === "must"}
        onCancelAdd={() => setAdding(null)}
        onSubmitAdd={(data) => add({ ...data, type: "must" })}
        defaultType="must"
        isClosed={isClosed}
      />

      {/* Nice-to-Have group */}
      <Group
        title="Kriteria Tambahan · Nice-to-Have"
        color="zinc"
        items={nice}
        onAdd={() => setAdding("nice")}
        renderItem={(c) =>
          editingId === c.id ? (
            <CriterionForm
              initial={c}
              onCancel={() => setEditingId(null)}
              onSubmit={(data) => update(c.id, data)}
            />
          ) : (
            <Row
              c={c}
              colorBand="zinc"
              onEdit={() => setEditingId(c.id)}
              onDelete={() => remove(c.id)}
              isClosed={isClosed}
            />
          )
        }
        adding={adding === "nice"}
        onCancelAdd={() => setAdding(null)}
        onSubmitAdd={(data) => add({ ...data, type: "nice" })}
        defaultType="nice"
        isClosed={isClosed}
      />

      {/* Education panel */}
      <EducationPanel job={job} onUpdate={onUpdate} isClosed={isClosed} />
    </div>
  );
}

function Group({ title, color, items, renderItem, onAdd, adding, onCancelAdd, onSubmitAdd, defaultType, isClosed }) {
  const headerCls =
    color === "emerald"
      ? "text-emerald-700"
      : color === "zinc"
      ? "text-zinc-700"
      : "text-zinc-700";

  return (
    <div className="bg-white border border-zinc-200 rounded-sm p-5">
      <div className="flex items-center justify-between mb-3">
        <div className={`text-xs uppercase tracking-wider font-medium ${headerCls}`}>
          {title}
        </div>
        {!isClosed && (
          <Button
            onClick={onAdd}
            variant="outline"
            size="sm"
            className="rounded-sm border-zinc-300 h-7 text-xs"
            data-testid={`add-${defaultType}-button`}
          >
            <Plus size={12} className="mr-1" /> Tambah
          </Button>
        )}
      </div>

      {items.length === 0 && !adding ? (
        <div className="text-sm text-zinc-400 py-2">Belum ada kriteria di kategori ini</div>
      ) : (
        <div className="space-y-1.5">
          {items.map((c) => (
            <div key={c.id} data-testid={`criterion-${c.id}`}>
              {renderItem(c)}
            </div>
          ))}
        </div>
      )}

      {adding && (
        <div className="mt-3 pt-3 border-t border-dashed border-zinc-200">
          <CriterionForm onCancel={onCancelAdd} onSubmit={onSubmitAdd} />
        </div>
      )}
    </div>
  );
}

function Row({ c, colorBand, onEdit, onDelete, isClosed }) {
  const bgCls =
    colorBand === "emerald"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : "bg-zinc-50 text-zinc-700 border-zinc-200";
  const catLabel = CATEGORIES.find((x) => x.value === c.category)?.label || c.category;
  return (
    <div className="flex items-center justify-between gap-2 px-3 py-2 border border-zinc-200 rounded-sm hover:border-zinc-400 transition-colors">
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <span className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 border rounded-sm ${bgCls} font-medium shrink-0`}>
          {catLabel}
        </span>
        <span className="text-sm text-zinc-900 truncate flex-1">{c.value}</span>
        <WeightChip weight={c.weight || 3} />
      </div>
      {!isClosed && (
        <div className="flex gap-1 shrink-0">
          <button
            onClick={onEdit}
            data-testid={`edit-criterion-${c.id}`}
            className="p-1.5 hover:bg-zinc-100 rounded-sm text-zinc-500 hover:text-zinc-900"
          >
            <Pencil size={12} />
          </button>
          <button
            onClick={onDelete}
            data-testid={`delete-criterion-${c.id}`}
            className="p-1.5 hover:bg-rose-50 rounded-sm text-zinc-500 hover:text-rose-700"
          >
            <Trash2 size={12} />
          </button>
        </div>
      )}
    </div>
  );
}

function WeightChip({ weight }) {
  const dotCls =
    weight >= 5 ? "bg-rose-600"
    : weight === 4 ? "bg-amber-500"
    : weight === 3 ? "bg-zinc-500"
    : "bg-zinc-300";
  return (
    <span className="inline-flex items-center gap-1 text-[10px] text-zinc-500 font-mono">
      <span className={`w-1.5 h-1.5 rounded-full ${dotCls}`} />
      Bobot {weight}
    </span>
  );
}

function CriterionForm({ initial, onCancel, onSubmit }) {
  const [value, setValue] = useState(initial?.value || "");
  const [category, setCategory] = useState(initial?.category || "skill");
  const [weight, setWeight] = useState(initial?.weight || 3);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!value.trim()) {
      toast.error("Isi nilai kriteria");
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit({
        value: value.trim(),
        category,
        weight,
        type: initial?.type || "must",
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-zinc-50/50 p-3 rounded-sm space-y-2 border border-zinc-200">
      <Input
        autoFocus
        placeholder="Contoh: Minimal 5 tahun pengalaman di bidang payroll"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="rounded-sm h-9 text-sm"
        data-testid="criterion-value-input"
      />
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] uppercase tracking-wider text-zinc-500">Kategori</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full border border-zinc-300 rounded-sm text-xs h-8 px-2 mt-1"
            data-testid="criterion-category-select"
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-wider text-zinc-500">
            Bobot: {WEIGHT_LABELS[weight]}
          </label>
          <input
            type="range"
            min={1}
            max={5}
            value={weight}
            onChange={(e) => setWeight(Number(e.target.value))}
            className="w-full mt-2 accent-zinc-900"
            data-testid="criterion-weight-input"
          />
        </div>
      </div>
      <div className="flex justify-end gap-2 pt-1">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onCancel}
          className="rounded-sm h-7 text-xs border-zinc-300"
        >
          <X size={12} className="mr-1" /> Batal
        </Button>
        <Button
          type="submit"
          size="sm"
          disabled={submitting}
          className="rounded-sm h-7 text-xs bg-zinc-900 hover:bg-zinc-800"
          data-testid="submit-criterion"
        >
          <Save size={12} className="mr-1" />
          {submitting ? "Menyimpan..." : "Simpan"}
        </Button>
      </div>
    </form>
  );
}

function EducationPanel({ job, onUpdate, isClosed }) {
  const [editing, setEditing] = useState(false);
  const [level, setLevel] = useState(job.education_level || "");
  const [major, setMajor] = useState(job.education_major || "");
  const [levelPct, setLevelPct] = useState(job.weights?.edu_level_pct ?? 70);
  const [submitting, setSubmitting] = useState(false);

  const save = async () => {
    setSubmitting(true);
    try {
      await api.patch(`/jobs/${job.id}/education`, {
        education_level: level,
        education_major: major,
        edu_level_pct: levelPct,
        edu_major_pct: 100 - levelPct,
      });
      toast.success("Pendidikan diperbarui");
      setEditing(false);
      onUpdate();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal menyimpan");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-white border border-zinc-200 rounded-sm p-5" data-testid="education-panel">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <GraduationCap size={14} className="text-zinc-700" />
          <div className="text-xs uppercase tracking-wider font-medium text-zinc-700">
            Pendidikan
          </div>
        </div>
        {!editing ? (
          !isClosed && (
            <Button
              onClick={() => setEditing(true)}
              variant="outline"
              size="sm"
              className="rounded-sm border-zinc-300 h-7 text-xs"
              data-testid="edit-education"
            >
              <Pencil size={12} className="mr-1" /> Edit
            </Button>
          )
        ) : (
          <div className="flex gap-2">
            <Button
              onClick={() => {
                setEditing(false);
                setLevel(job.education_level || "");
                setMajor(job.education_major || "");
                setLevelPct(job.weights?.edu_level_pct ?? 70);
              }}
              variant="outline"
              size="sm"
              className="rounded-sm border-zinc-300 h-7 text-xs"
            >
              Batal
            </Button>
            <Button
              onClick={save}
              size="sm"
              disabled={submitting}
              className="rounded-sm h-7 text-xs bg-zinc-900 hover:bg-zinc-800"
              data-testid="save-education"
            >
              <Save size={12} className="mr-1" /> Simpan
            </Button>
          </div>
        )}
      </div>

      {!editing ? (
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">
              Jenjang Minimum (bobot {job.weights?.edu_level_pct ?? 70}%)
            </div>
            <div className="font-medium" data-testid="education-level-display">
              {job.education_level || "—"}
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">
              Jurusan (bobot {job.weights?.edu_major_pct ?? 30}%)
            </div>
            <div className="font-medium" data-testid="education-major-display">
              {job.education_major || "Semua jurusan"}
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-zinc-500">
                Jenjang Minimum
              </label>
              <select
                value={level}
                onChange={(e) => setLevel(e.target.value)}
                className="w-full border border-zinc-300 rounded-sm text-sm h-9 px-2 mt-1"
                data-testid="education-level-select"
              >
                <option value="">— Tidak Spesifik —</option>
                {EDU_LEVELS.map((lv) => (
                  <option key={lv} value={lv}>{lv}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-zinc-500">
                Jurusan
              </label>
              <Input
                value={major}
                onChange={(e) => setMajor(e.target.value)}
                placeholder="Contoh: Akuntansi (kosongkan utk semua jurusan)"
                className="rounded-sm h-9 mt-1 text-sm"
                data-testid="education-major-input"
              />
            </div>
          </div>
          <div className="pt-2">
            <div className="flex justify-between items-baseline mb-1.5">
              <label className="text-[10px] uppercase tracking-wider text-zinc-500">
                Distribusi Bobot
              </label>
              <span className="text-xs font-mono tabular-nums">
                Jenjang {levelPct}% · Jurusan {100 - levelPct}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              step={10}
              value={levelPct}
              onChange={(e) => setLevelPct(Number(e.target.value))}
              className="w-full accent-zinc-900"
              data-testid="education-weight-slider"
            />
            <div className="text-[10px] text-zinc-400 mt-1 italic">
              Geser ke kiri untuk fokus pada jurusan; ke kanan untuk fokus jenjang. Jika "semua jurusan", set 100%/0%.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
