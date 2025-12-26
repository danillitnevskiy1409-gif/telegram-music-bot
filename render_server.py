# -*- coding: utf-8 -*-
"""
Bot de descarga de musica para Telegram
Servidor para Render.com
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import subprocess
import os
import re
from pathlib import Path
import base64
import uvicorn

app = FastAPI()


def clean_filename(filename: str) -> str:
    """Limpia el nombre del archivo"""
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    if len(filename) > 200:
        filename = filename[:200]
    return filename


def download_audio(url: str = None, search_query: str = None) -> dict:
    """
    Descarga audio de YouTube o busqueda

    Args:
        url: Link directo de YouTube/Spotify
        search_query: Termino de busqueda

    Returns:
        dict con resultado de la descarga
    """
    try:
        output_dir = "/tmp/music"
        os.makedirs(output_dir, exist_ok=True)

        # Limpiar descargas anteriores
        for f in Path(output_dir).glob("*"):
            try:
                f.unlink()
            except:
                pass

        # Determinar la URL a descargar
        download_url = url

        if search_query and not url:
            download_url = f"ytsearch1:{search_query}"
        elif url and "spotify.com" in url:
            download_url = f"ytsearch1:{url}"

        if not download_url:
            return {
                "success": False,
                "error": "No se proporciono URL ni busqueda"
            }

        output_template = os.path.join(output_dir, "%(title)s.%(ext)s")

        cmd = [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--embed-thumbnail",
            "--add-metadata",
            "-o", output_template,
            download_url,
            "--no-warnings",
            "--no-playlist",
        ]

        print(f"Ejecutando: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout
            return {
                "success": False,
                "error": f"Error en yt-dlp: {error_msg[:500]}"
            }

        mp3_files = list(Path(output_dir).glob("*.mp3"))

        if not mp3_files:
            return {
                "success": False,
                "error": "No se encontro archivo MP3 despues de la descarga"
            }

        mp3_file = mp3_files[0]
        file_size = mp3_file.stat().st_size

        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            return {
                "success": False,
                "error": f"El archivo es muy grande ({file_size / 1024 / 1024:.1f}MB). Maximo: 50MB"
            }

        with open(mp3_file, "rb") as f:
            file_data = f.read()

        file_data_b64 = base64.b64encode(file_data).decode()

        return {
            "success": True,
            "file_data": file_data_b64,
            "filename": clean_filename(mp3_file.stem) + ".mp3",
            "title": mp3_file.stem,
            "file_size": file_size,
            "size_mb": round(file_size / 1024 / 1024, 2)
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "La descarga tardo demasiado (timeout)"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error inesperado: {str(e)}"
        }


@app.get("/")
async def root():
    """Endpoint de prueba"""
    return {"status": "ok", "message": "Telegram Music Bot API"}


@app.post("/")
async def webhook(request: Request):
    """
    Endpoint webhook para n8n
    Recibe JSON con url o search_query
    """
    try:
        data = await request.json()
        url = data.get("url")
        search_query = data.get("search_query")

        result = download_audio(url=url, search_query=search_query)

        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
