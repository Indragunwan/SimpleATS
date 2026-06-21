# PDF Extractor GUI

Aplikasi desktop sederhana untuk mengekstrak konten PDF menggunakan [opendataloader-pdf](https://github.com/opendataloader-project/opendataloader-pdf).

## Prasyarat

- Python 3.10+
- Java 11+ (wajib untuk opendataloader-pdf) — install dari [Adoptium](https://adoptium.net/)

## Install

```bash
pip install -r requirements.txt
```

## Jalankan

```bash
python app.py
```

## Cara Pakai

1. Klik **Browse…** → pilih file PDF
2. Pilih format output: `markdown` / `json` / `html` / `text`
3. Klik **Extract** → hasil tampil di panel bawah

## Format Output

| Format   | Kegunaan                                  |
|----------|-------------------------------------------|
| markdown | Teks terstruktur untuk LLM / RAG          |
| json     | Data + bounding box per elemen            |
| html     | Tampilan web                              |
| text     | Teks polos                                |
