from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
import platform
import tempfile
import subprocess
import os
import sys

app = FastAPI(title="Local Print Agent")

TOKEN_FILE = os.path.join(os.path.dirname(__file__), 'agent.token')

def load_token():
    try:
        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return None

_TOKEN = load_token()

def check_token(header_token: str):
    if _TOKEN and header_token != _TOKEN:
        raise HTTPException(status_code=401, detail='Invalid token')

def get_default_printer_name():
    if platform.system() == 'Windows':
        try:
            import win32print
            return win32print.GetDefaultPrinter()
        except Exception:
            return None
    else:
        # Try lpstat
        try:
            out = subprocess.check_output(['lpstat', '-d'], stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
            # line like "system default destination: PRINTER"
            if ':' in out:
                return out.split(':',1)[1].strip()
        except Exception:
            return None
    return None

def print_bytes_to_default(data: bytes):
    system = platform.system()
    if system == 'Windows':
        try:
            import win32print
            hPrinter = win32print.OpenPrinter(win32print.GetDefaultPrinter())
            try:
                win32print.StartDocPrinter(hPrinter, 1, ("Ticket", None, "RAW"))
                win32print.StartPagePrinter(hPrinter)
                win32print.WritePrinter(hPrinter, data)
                win32print.EndPagePrinter(hPrinter)
                win32print.EndDocPrinter(hPrinter)
            finally:
                win32print.ClosePrinter(hPrinter)
            return True
        except Exception as e:
            raise
    else:
        # Write to temp file and call lp
        fd, fname = tempfile.mkstemp(prefix='print_agent_', suffix='.bin')
        os.close(fd)
        try:
            with open(fname, 'wb') as f:
                f.write(data)
            subprocess.run(['lp', fname], check=True)
            return True
        finally:
            try:
                os.unlink(fname)
            except Exception:
                pass

@app.get('/ping')
async def ping():
    return JSONResponse({'ok': True, 'printer': get_default_printer_name()})

@app.get('/info')
async def info():
    return JSONResponse({'printer': get_default_printer_name(), 'platform': platform.system()})

@app.post('/print/raw')
async def print_raw(request: Request, x_print_token: str = Header(None)):
    check_token(x_print_token)
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail='Empty body')
    try:
        print_bytes_to_default(body)
        return JSONResponse({'ok': True})
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/print/html')
async def print_html(request: Request, x_print_token: str = Header(None)):
    check_token(x_print_token)
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail='Empty body')
    # For PoC we send HTML text directly to printer as UTF-8 bytes; many receipt printers will accept plain text
    try:
        print_bytes_to_default(data)
        return JSONResponse({'ok': True})
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/pair')
async def pair(token: str):
    # Store token for future requests
    try:
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            f.write(token)
        return JSONResponse({'ok': True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='127.0.0.1', port=34567)
