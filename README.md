# Odoo Senjani - Run Guide

## Menjalankan Project

Jalankan dari root project:

```powershell
docker compose up -d
```

Cek status container:

```powershell
docker compose ps
```

Container yang seharusnya aktif:

- odoo18-db
- odoo18-app

Akses aplikasi di browser:

```text
http://localhost:8069
```

## Perintah Penting

Lihat semua log:

```powershell
docker compose logs -f
```

Lihat log Odoo saja:

```powershell
docker compose logs -f odoo
```

Stop service:

```powershell
docker compose down
```

Reset data (hapus volume):

```powershell
docker compose down -v
```

## Troubleshooting Cepat

Jika Odoo tidak bisa dibuka:

```powershell
docker compose ps
docker compose logs db
docker compose logs odoo
```

Jika port 8069 bentrok, ubah mapping port di docker-compose.yml lalu restart:

```powershell
docker compose down
docker compose up -d
```
