with open('src/pages/JobDetail.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# Add states
old_states = 'const [reprocessingIds, setReprocessingIds] = useState(new Set());'
new_states = """const [reprocessingIds, setReprocessingIds] = useState(new Set());
  const [rescreenAllOpen, setRescreenAllOpen] = useState(false);
  const [rescreeningAll, setRescreeningAll] = useState(false);

  const formatDuration = (seconds) => {
    if (seconds < 60) return `${seconds} detik`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return secs > 0 ? `${mins} menit ${secs} detik` : `${mins} menit`;
  };

  const formatRupiah = (amount) => {
    return new Intl.NumberFormat("id-ID").format(amount);
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
  };"""

if 'const [rescreenAllOpen, setRescreenAllOpen]' not in text:
    text = text.replace(old_states, new_states)

# Add "Proses Ulang Semua" button next to Search
old_search_start = '<div className="flex items-center gap-2">\n            <div className="relative">'
new_search_start = """<div className="flex items-center gap-2">
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
            <div className="relative">"""

if 'setRescreenAllOpen(true)' not in text:
    text = text.replace(old_search_start, new_search_start)

# Add modal block right before the closing div of the page
# Let's locate the end of the JobDetail component
# We find:
#       {poolOpen && (
#         <SuggestFromPoolDialog
#           jobId={id}
#           onClose={() => setPoolOpen(false)}
#           onQueued={() => {
#             setPoolOpen(false);
#             setTimeout(load, 1500);
#           }}
#         />
#       )}
#     </div>
#   );
# }

old_suggest_modal_end = """      {poolOpen && (
        <SuggestFromPoolDialog
          jobId={id}
          onClose={() => setPoolOpen(false)}
          onQueued={() => {
            setPoolOpen(false);
            setTimeout(load, 1500);
          }}
        />
      )}"""

new_suggest_modal_end = """      {poolOpen && (
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
      )}"""

if 'Proses Ulang Semua CV' not in text:
    text = text.replace(old_suggest_modal_end, new_suggest_modal_end)

with open('src/pages/JobDetail.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("JobDetail.jsx patched with rescreen all features.")
