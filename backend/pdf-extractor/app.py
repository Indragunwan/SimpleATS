import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import tempfile
import os
import json
import shutil
import urllib.request

try:
    import opendataloader_pdf
    ODL_AVAILABLE = True
except ImportError:
    ODL_AVAILABLE = False

JAVA_AVAILABLE = shutil.which("java") is not None

LLM_BASE_URL = "https://api.freemodel.dev/v1"
LLM_API_KEY  = "fe_oa_ad25557f7d24ed2366fec8d0c2f561c78733d274087a0ccd"
LLM_MODEL    = "gpt-5.4-mini"

REFINE_PROMPT = """You are a Markdown formatting assistant.
The text below is raw Markdown extracted from a PDF. Clean it up:
- Fix reading order issues in multi-column layouts
- Separate table category headers into proper Markdown headings (### Heading)
- Fix merged list items — each bullet/numbered item on its own line
- Fix table of contents formatting
- Do NOT change content, translate, or summarize
- Return only the cleaned Markdown, no explanation

---
{content}
"""


CHUNK_CHARS = 6000  # ~1500 tokens per chunk, safe under timeout


def _llm_call(content: str) -> str:
    payload = json.dumps({
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": REFINE_PROMPT.format(content=content)}],
        "temperature": 0.1,
    }).encode()
    req = urllib.request.Request(
        f"{LLM_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


def llm_refine(content: str) -> str:
    if len(content) <= CHUNK_CHARS:
        return _llm_call(content)
    # Split by double newline to preserve paragraph boundaries
    paragraphs, chunk, chunks = content.split("\n\n"), [], []
    for p in paragraphs:
        if sum(len(c) for c in chunk) + len(p) > CHUNK_CHARS and chunk:
            chunks.append("\n\n".join(chunk))
            chunk = []
        chunk.append(p)
    if chunk:
        chunks.append("\n\n".join(chunk))
    return "\n\n".join(_llm_call(c) for c in chunks)


class PDFExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Extractor — opendataloader-pdf")
        self.root.geometry("1000x680")
        self.pdf_path = None
        self._build_ui()

    def _build_ui(self):
        # Top bar: file picker + format + extract button
        top = tk.Frame(self.root, pady=8, padx=10)
        top.pack(fill=tk.X)

        tk.Label(top, text="PDF File:").pack(side=tk.LEFT)
        self.path_var = tk.StringVar(value="No file selected")
        tk.Label(top, textvariable=self.path_var, fg="gray", width=40, anchor="w").pack(side=tk.LEFT, padx=(4, 10))
        tk.Button(top, text="Browse…", command=self._browse).pack(side=tk.LEFT)

        tk.Label(top, text="Format:").pack(side=tk.LEFT, padx=(20, 4))
        self.fmt_var = tk.StringVar(value="markdown")
        fmt_cb = ttk.Combobox(top, textvariable=self.fmt_var, width=10,
                               values=["markdown", "json", "html", "text"], state="readonly")
        fmt_cb.pack(side=tk.LEFT)

        self.extract_btn = tk.Button(top, text="Extract", bg="#2563eb", fg="white",
                                     padx=12, command=self._start_extract)
        self.extract_btn.pack(side=tk.LEFT, padx=(16, 0))

        self.save_btn = tk.Button(top, text="Save As…", padx=10, command=self._save_as,
                                  state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.refine_var = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text="AI Refine", variable=self.refine_var).pack(side=tk.LEFT, padx=(16, 0))

        self.hybrid_var = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text="Hybrid Mode", variable=self.hybrid_var).pack(side=tk.LEFT, padx=(8, 0))

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(top, textvariable=self.status_var, fg="#64748b").pack(side=tk.RIGHT)

        # Warning if library not installed
        if not ODL_AVAILABLE:
            warn = tk.Label(self.root,
                            text="⚠  opendataloader-pdf not installed. Run: pip install opendataloader-pdf",
                            bg="#fef3c7", fg="#92400e", pady=4)
            warn.pack(fill=tk.X, padx=10)

        if not JAVA_AVAILABLE:
            warn2 = tk.Label(self.root,
                             text="⚠  Java tidak ditemukan di PATH. Install JDK 11+ dari https://adoptium.net/ lalu restart.",
                             bg="#fee2e2", fg="#991b1b", pady=4)
            warn2.pack(fill=tk.X, padx=10)

        # Preview area
        self.preview = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, font=("Consolas", 10),
                                                  state=tk.DISABLED, bg="#f8fafc")
        self.preview.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    def _browse(self):
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if path:
            self.pdf_path = path
            self.path_var.set(os.path.basename(path))

    def _start_extract(self):
        if not self.pdf_path:
            messagebox.showwarning("No file", "Please select a PDF file first.")
            return
        if not ODL_AVAILABLE:
            messagebox.showerror("Library missing",
                                 "Install opendataloader-pdf:\n  pip install opendataloader-pdf")
            return
        if not JAVA_AVAILABLE:
            messagebox.showerror(
                "Java tidak ditemukan",
                "Java (JDK 11+) harus terinstall dan ada di PATH.\n\n"
                "1. Download dari: https://adoptium.net/\n"
                "2. Install, centang opsi 'Add to PATH'\n"
                "3. Buka terminal baru, cek: java -version\n"
                "4. Restart aplikasi ini"
            )
            return
        if self.hybrid_var.get():
            try:
                import docling  # noqa: F401
            except ImportError:
                messagebox.showerror(
                    "Hybrid tidak terinstall",
                    "Jalankan dulu:\n  pip install \"opendataloader-pdf[hybrid]\"\nlalu restart aplikasi."
                )
                return
            import urllib.request as _ur
            try:
                _ur.urlopen("http://localhost:5002/health", timeout=2)
            except Exception:
                messagebox.showerror(
                    "Hybrid server tidak berjalan",
                    "Buka terminal baru dan jalankan:\n\n"
                    "  opendataloader-pdf-hybrid --port 5002\n\n"
                    "Tunggu sampai server siap, lalu klik Extract lagi."
                )
                return
        self.extract_btn.config(state=tk.DISABLED)
        self.status_var.set("Extracting…")
        threading.Thread(target=self._extract, daemon=True).start()

    def _extract(self):
        fmt = self.fmt_var.get()
        use_hybrid = self.hybrid_var.get()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                kwargs = dict(input_path=[self.pdf_path], output_dir=tmp, format=fmt)
                if use_hybrid:
                    kwargs["hybrid"] = "docling-fast"
                    kwargs["hybrid_fallback"] = True
                opendataloader_pdf.convert(**kwargs)
                content = self._read_output(tmp, fmt)
            # tmp folder is now deleted — content already read above
            if self.refine_var.get() and fmt in ("markdown", "text", "html"):
                self.root.after(0, lambda: self.status_var.set("AI Refining…"))
                content = llm_refine(content)
            self.root.after(0, self._show_result, content)
        except FileNotFoundError as e:
            if "java" in str(e).lower() or "WinError 2" in str(e):
                msg = (
                    "Java tidak ditemukan di PATH.\n\n"
                    "Solusi:\n"
                    "1. Install JDK 11+ dari https://adoptium.net/\n"
                    "2. Pastikan java.exe ada di PATH\n"
                    "3. Buka terminal baru lalu cek: java -version\n"
                    "4. Jalankan ulang aplikasi ini"
                )
            else:
                msg = str(e)
            self.root.after(0, self._show_error, msg)
        except Exception as e:
            self.root.after(0, self._show_error, str(e))

    def _read_output(self, directory, fmt):
        ext_map = {"markdown": ".md", "json": ".json", "html": ".html", "text": ".txt"}
        ext = ext_map.get(fmt, f".{fmt}")
        for fname in os.listdir(directory):
            if fname.endswith(ext):
                fpath = os.path.join(directory, fname)
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
                # Pretty-print JSON
                if fmt == "json":
                    try:
                        content = json.dumps(json.loads(content), indent=2, ensure_ascii=False)
                    except Exception:
                        pass
                return content
        return f"(No {ext} output file found in {directory})\n\nFiles: {os.listdir(directory)}"

    def _show_result(self, content):
        self.preview.config(state=tk.NORMAL)
        self.preview.delete("1.0", tk.END)
        self.preview.insert(tk.END, content)
        self.preview.config(state=tk.DISABLED)
        self.status_var.set(f"Done — {len(content):,} chars")
        self.extract_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.NORMAL)

    def _show_error(self, msg):
        self.preview.config(state=tk.NORMAL)
        self.preview.delete("1.0", tk.END)
        self.preview.insert(tk.END, f"Error:\n{msg}")
        self.preview.config(state=tk.DISABLED)
        self.status_var.set("Error")
        self.extract_btn.config(state=tk.NORMAL)

    def _save_as(self):
        fmt = self.fmt_var.get()
        ext_map = {"markdown": ".md", "json": ".json", "html": ".html", "text": ".txt"}
        ext = ext_map.get(fmt, f".{fmt}")
        default = os.path.splitext(os.path.basename(self.pdf_path or "output"))[0] + ext
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            initialfile=default,
            filetypes=[(f"{fmt.upper()} files", f"*{ext}"), ("All files", "*.*")],
        )
        if not path:
            return
        content = self.preview.get("1.0", tk.END)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        self.status_var.set(f"Saved → {os.path.basename(path)}")


if __name__ == "__main__":
    root = tk.Tk()
    PDFExtractorApp(root)
    root.mainloop()
