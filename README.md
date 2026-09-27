# MEPConnect — Deploy-Ready B2B MEP Procurement MVP

MEPConnect adalah platform B2B digital procurement untuk material Mechanical, Electrical, Plumbing, dan Fire Protection pada proyek bangunan gedung.

## Fitur MVP
- Registrasi buyer/supplier
- Login/logout dengan password hashing
- Katalog material MEP
- Pencarian produk
- Pemesanan dan pengurangan stok
- Dashboard buyer dan supplier
- Tambah produk supplier
- RFQ marketplace
- Supplier mengirim quotation
- Update status order: Processing → Shipped → Delivered
- Health check: `/health`
- PostgreSQL untuk deployment production; SQLite tetap tersedia untuk pengembangan lokal

## Akun demo
Buyer:
- Email: `buyer@mepconnect.local`
- Password: `buyer123`

Supplier:
- Email: `supplier@mepconnect.local`
- Password: `supplier123`

**Ganti/hapus akun demo sebelum website digunakan untuk transaksi nyata.**

## Menjalankan lokal
Python 3.13 direkomendasikan.

Windows:
```powershell
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
$env:COOKIE_SECURE="0"
python app.py
```

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export COOKIE_SECURE=0
python app.py
```

Buka `http://127.0.0.1:5000`.

## Deploy ke Render
Render mendukung Flask dengan Gunicorn. Paket ini sudah menyediakan `render.yaml`.

1. Buat repository GitHub baru, misalnya `mepconnect`.
2. Upload seluruh isi folder ini ke repository tersebut.
3. Di Render pilih **New → Web Service** dan hubungkan repository.
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn --workers 2 --threads 4 --timeout 120 app:app`
6. Buat PostgreSQL database di Render.
7. Salin **internal database URL** database tersebut ke environment variable `DATABASE_URL` pada web service.
8. Pastikan `SECRET_KEY` menggunakan nilai rahasia yang kuat dan `COOKIE_SECURE=1`.
9. Deploy. Setelah selesai, gunakan URL `.onrender.com` yang diberikan Render.

Alternatifnya, gunakan Blueprint `render.yaml` yang sudah tersedia, lalu isi `DATABASE_URL` saat diminta.

## Docker
```bash
docker build -t mepconnect .
docker run --rm -p 10000:10000 \
  -e SECRET_KEY="change-this" \
  -e COOKIE_SECURE=0 \
  -e DATABASE_URL="sqlite:////app/mepconnect.db" \
  mepconnect
```

## Environment variables
- `SECRET_KEY` — wajib diganti dengan secret acak pada production.
- `DATABASE_URL` — URL PostgreSQL production atau SQLite lokal.
- `COOKIE_SECURE` — `1` pada HTTPS production, `0` untuk local HTTP.
- `PORT` — port dari platform hosting; Gunicorn/Flask akan membacanya pada konfigurasi yang sesuai.

## Catatan production
MVP ini sudah disiapkan untuk deployment, tetapi masih bukan sistem e-commerce enterprise penuh. Sebelum menerima transaksi nyata, tambahkan:
- Payment gateway dan rekonsiliasi pembayaran
- Verifikasi legalitas supplier dan proses approval admin
- Upload datasheet/sertifikasi ke object storage
- Email/WhatsApp/OTP notification
- CSRF protection pada seluruh form
- Rate limiting dan monitoring
- Audit log transaksi
- Backup dan migration database
- Role admin dan approval quotation/PO
- Pembuatan PO/invoice PDF
- Integrasi ongkir/logistik
- Terms, privacy policy, refund, dan dokumen legal bisnis
