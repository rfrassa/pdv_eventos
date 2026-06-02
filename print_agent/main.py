from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
import platform
import tempfile
import subprocess
import os
import sys
import shutil

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


def find_chrome_executable():
    # Try common Chrome/Edge paths, then try executable names in PATH
    system = platform.system()
    candidates = []
    if system == 'Windows':
        program_files = os.environ.get('ProgramFiles', r'C:\Program Files')
        program_files_x86 = os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')
        candidates += [
            os.path.join(program_files, 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(program_files_x86, 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(program_files, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
            os.path.join(program_files_x86, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
        ]
        candidates += ['chrome.exe', 'msedge.exe']
    else:
        candidates += ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser']
        candidates += ['google-chrome', 'chromium', 'chromium-browser']

    for c in candidates:
        try:
            if os.path.isabs(c) and os.path.exists(c):
                return c
            else:
                # try which
                p = shutil.which(c)
                if p:
                    return p
        except Exception:
            continue
    return None


def render_html_to_pdf(html: str):
    """Render HTML to PDF using headless Chrome/Edge if available. Returns pdf path or None."""
    chrome = find_chrome_executable()
    if not chrome:
        return None
    fd, html_path = tempfile.mkstemp(prefix='print_agent_html_', suffix='.html')
    os.close(fd)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    pdf_fd, pdf_path = tempfile.mkstemp(prefix='print_agent_pdf_', suffix='.pdf')
    os.close(pdf_fd)
    try:
        cmd = [chrome, '--headless', '--no-sandbox', '--disable-gpu', f'--print-to-pdf={pdf_path}', html_path]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return pdf_path
    except Exception:
        try:
            if os.path.exists(pdf_path): os.unlink(pdf_path)
        except Exception:
            pass
    finally:
        try:
            if os.path.exists(html_path): os.unlink(html_path)
        except Exception:
            pass
    return None


def print_pdf(pdf_path: str):
    system = platform.system()
    try:
        if system == 'Windows':
            # Try SumatraPDF if installed
            sumatra = shutil.which('SumatraPDF.exe') or shutil.which('SumatraPDF')
            if sumatra:
                # print to default
                subprocess.run([sumatra, '-print-to-default', pdf_path], check=True)
                return True
            # Fallback: os.startfile print (may show UI depending on default app)
            try:
                os.startfile(pdf_path, 'print')
                return True
            except Exception:
                # last resort: attempt to use rundll32 (not reliable)
                return False
        else:
            subprocess.run(['lp', pdf_path], check=True)
            return True
    finally:
        try:
            os.unlink(pdf_path)
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
    html = data.decode('utf-8', errors='ignore')
    # Try render to PDF via headless Chrome/Edge and print PDF, fallback to raw bytes
    try:
        pdf = render_html_to_pdf(html)
        if pdf:
            ok = print_pdf(pdf)
            if ok:
                return JSONResponse({'ok': True, 'method': 'pdf'})
        # fallback: send bytes directly
        print_bytes_to_default(data)
        return JSONResponse({'ok': True, 'method': 'raw'})
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
        # Update in-memory token so agent accepts it immediately
        global _TOKEN
        _TOKEN = token
        return JSONResponse({'ok': True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='127.0.0.1', port=34567)
