import asyncio
from ai_service import extract_jd_criteria

async def main():
    text = '''Teks JD / Tanggung Jawab:
- Mengelola administrasi kantor
- Melakukan koordinasi antar divisi
- Menjaga kebersihan lingkungan

Teks Spesifikasi / Kualifikasi:
- Pendidikan minimal S1 Administrasi Bisnis
- Pengalaman 3 tahun
- Bisa Microsoft Office
- Komunikatif'''
    res = await extract_jd_criteria(text, {})
    print(res)

asyncio.run(main())
