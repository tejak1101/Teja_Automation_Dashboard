# Work Tracker Dashboard (Streamlit + Postgres)

Dashboard buat tracking task per-project (kayak project Dylan), bisa di-edit/hapus/tambah oleh Teja & Carl. Data disimpan permanen di database Postgres (Supabase), jadi aman walau di-redeploy.

## Fitur
- **Multi-project** — bikin project sebanyak yang perlu, masing-masing punya tracker & chat sendiri.
- **Task Tracker** — kanban 4 kolom, search, filter by assignee, toggle sembunyikan task Done, indikator **overdue** otomatis (merah kalau lewat due date).
- **Resources** — tempat nyimpen link penting per project (Google Drive, ClickUp, dokumen, dll), dikelompokkan per kategori.
- **Chat** — chat real-time antara Teja & Carl per project, support **@mention** (ketik `@Teja` atau `@Carl`).
- **Activity Log** — riwayat siapa nambah/edit/hapus apa, otomatis tercatat.
- **Overview** — ringkasan lintas semua project: total task, overdue, upcoming deadlines.
- **Notifikasi mention (opsional)** — kalau di-mention di chat, app bisa kirim data ke webhook Zapier kamu, lalu dari Zapier-nya tinggal di-routing ke email/WhatsApp/Discord/apapun sesuai automation yang udah kamu punya.

## Struktur file
- `app.py` — aplikasi utamanya
- `requirements.txt` — dependencies
- `secrets_example.toml` — contoh config (JANGAN di-commit ke GitHub kalau sudah diisi password asli)

Tabel database (`projects`, `tasks`, `chat_messages`) otomatis dibuat sendiri saat app pertama kali jalan — tidak perlu setup manual.

---

## 1. Bikin database gratis (Supabase)

1. Daftar/login di https://supabase.com → buat project baru (pilih region Singapore biar cepat).
2. Setelah project jadi, buka **Project Settings → Database → Connection string**, pilih tab **URI**.
3. Copy connection string-nya, isi password sesuai yang kamu set waktu bikin project.
4. Simpan string ini, dipakai di step 3 bawah.

## 2. Setup local (opsional, buat testing dulu sebelum deploy)

```bash
pip install -r requirements.txt
mkdir .streamlit
cp secrets_example.toml .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml`, isi:
- `postgres.url` → connection string dari Supabase
- `users.Teja` dan `users.Carl` → password bebas buat login masing-masing

Jalankan:
```bash
streamlit run app.py
```

## 3. Deploy ke Streamlit Community Cloud (gratis)

1. Push folder ini ke repo GitHub baru (private repo juga bisa).
   - **Jangan** ikut push file `.streamlit/secrets.toml` yang sudah ada password asli (tambahkan ke `.gitignore`).
2. Buka https://share.streamlit.io → **New app** → connect ke repo GitHub kamu.
3. Set **Main file path** = `app.py`.
4. Sebelum deploy, buka **Advanced settings → Secrets**, paste isi `secrets_example.toml` yang sudah kamu isi connection string Supabase + password Teja & Carl.
5. Klik **Deploy**. Tunggu build selesai → dapat link `https://xxxxx.streamlit.app` yang bisa dibuka Carl juga.

## 4. (Opsional) Aktifkan notifikasi mention via Zapier

Fitur ini bikin app kirim data ke Zapier setiap kali ada yang di-mention (`@Teja` / `@Carl`) di chat. Dari situ kamu bisa bikin Zap yang lanjutkan ke email, WhatsApp (via GHL/Twilio), atau Discord — bebas.

1. Di Zapier, buat Zap baru dengan trigger **Webhooks by Zapier → Catch Hook**.
2. Copy Catch Hook URL-nya (formatnya mirip base webhook kamu yang sudah ada: `https://hooks.zapier.com/hooks/catch/26963912/xxxxxxx/`).
3. Payload yang dikirim app ke webhook ini berupa JSON:
   ```json
   {
     "project": "Nama Project",
     "sender": "Teja",
     "mentioned": "Carl",
     "message": "Isi pesan chat...",
     "timestamp": "2026-07-10T10:00:00"
   }
   ```
4. Tambahkan action lanjutan di Zap (kirim email via Gmail, kirim WA via GHL, atau post ke Discord) sesuai kebutuhan.
5. Tambahkan URL webhook itu ke `secrets.toml`:
   ```toml
   [notifications]
   webhook_url = "https://hooks.zapier.com/hooks/catch/26963912/xxxxxxx/"
   ```
6. Kalau bagian `[notifications]` ini tidak diisi/dihapus, fitur notifikasi otomatis nonaktif — chat tetap jalan normal seperti biasa, cuma tanpa notif keluar.

## 5. Cara pakai

- Login pilih user (Teja/Carl) + password masing-masing.
- Sidebar: pilih project atau bikin project baru (misal "Project Dylan", "Project X").
- Tab **Task Tracker**: kanban board (To Do / In Progress / Review / Done), tambah task via tombol "➕ Tambah task baru", edit/hapus via "Detail / Edit" di tiap card.
- Tab **Chat**: chat langsung dengan Carl, otomatis refresh tiap 5 detik.

## Catatan
- Kalau nanti mau tambah user ketiga, tinggal tambah baris baru di `[users]` pada secrets.
- Supabase free tier cukup untuk kebutuhan ini (limit lumayan besar untuk skala tim kecil).
- Kalau mau custom status atau kolom lain (misal ClickUp task ID, link Drive), tinggal bilang — gampang ditambah di kode.