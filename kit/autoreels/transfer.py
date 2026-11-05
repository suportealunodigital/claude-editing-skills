"""Bounded streaming transfers. URLs/tokens never enter manifests or error text."""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit, parse_qs, urlencode
from html.parser import HTMLParser

import httpx

DRIVE_HOSTS = {'drive.google.com', 'drive.usercontent.google.com', 'www.googleapis.com'}
MAX_BYTES = 2 * 1024**3
CHUNK = 8 * 1024**2

class TransferError(ValueError):
    pass


def check_url(url, allowed):
    try:
        p = urlsplit(url)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.fragment or p.port not in (None, 443):
            raise ValueError()
        host = p.hostname.lower()
        drive_redirect = 'drive.usercontent.google.com' in allowed and re.fullmatch(r'doc-[a-z0-9-]+\.googleusercontent\.com', host)
        if (host not in allowed and not drive_redirect) or host == 'localhost' or host.endswith(('.local', '.internal')):
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError()
        if host == 'github.com' or host.endswith(('.githubusercontent.com', '.github.io')):
            raise ValueError()
    except (ValueError, TypeError):
        raise TransferError('HTTPS destination is not an approved private-media storage host.') from None
    return host


def check_network(host, policy_path=Path('/etc/codex/network-policy.json')):
    if not policy_path.exists():
        return  # actual request is still subject to the executor's enforced policy
    try:
        policy = json.loads(policy_path.read_text()).get('http_network_policy', {})
    except (ValueError, OSError):
        raise TransferError('Cannot read the executor network policy.') from None
    if policy.get('type') == 'restricted':
        hosts = {x.get('host') for x in policy.get('egress_rules', [])}
        if host not in hosts:
            raise TransferError(f'Executor network policy does not allow {host}; configure the active Cloud environment.')


def drive_id(url):
    check_url(url, DRIVE_HOSTS)
    p = urlsplit(url)
    q = parse_qs(p.query)
    match = re.search(r'/file/d/([A-Za-z0-9_-]+)', p.path)
    fid = match.group(1) if match else q.get('id', [''])[0]
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,200}', fid):
        raise TransferError('Use a Google Drive file link, not a folder or Google Docs link.')
    key = q.get('resourcekey', [''])[0]
    if key and not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', key):
        raise TransferError('Invalid Drive resource key.')
    return fid, key


class DownloadForm(HTMLParser):
    def __init__(self):
        super().__init__(); self.action = None; self.fields = {}; self.inside = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form' and a.get('id') == 'download-form':
            self.action = a.get('action'); self.inside = True
        elif self.inside and tag == 'input' and a.get('type') == 'hidden' and a.get('name'):
            self.fields[a['name']] = a.get('value', '')
    def handle_endtag(self, tag):
        if tag == 'form': self.inside = False


class Storage:
    def __init__(self, max_bytes=MAX_BYTES, client=None, policy_path=Path('/etc/codex/network-policy.json')):
        self.max_bytes = max_bytes
        self.client = client or httpx.Client(timeout=httpx.Timeout(90, connect=20), follow_redirects=False, headers={'Accept-Encoding':'identity'})
        self.owned = client is None
        self.policy_path = policy_path
    def close(self):
        if self.owned: self.client.close()
    def permit(self, url, allowed):
        check_network(check_url(url, allowed), self.policy_path)
    def get_json(self, url, headers):
        self.permit(url, {'www.googleapis.com'})
        try:
            r = self.client.get(url, headers=headers)
            if r.status_code != 200: raise TransferError(f'Drive metadata denied (HTTP {r.status_code}); check account permission and OAuth scope.')
            return r.json()
        except httpx.HTTPError:
            raise TransferError('Drive metadata network/TLS request failed; signed URLs and tokens omitted.') from None
    def download_drive(self, url, destination, token=None):
        fid, key = drive_id(url)
        headers = {}
        if token:
            headers['Authorization'] = 'Bearer ' + token
            if key: headers['X-Goog-Drive-Resource-Keys'] = fid + '/' + key
            meta = self.get_json('https://www.googleapis.com/drive/v3/files/'+fid+'?fields=name,size,mimeType,trashed,capabilities', headers)
            if meta.get('trashed') or meta.get('capabilities', {}).get('canDownload') is False:
                raise TransferError('This account is not allowed to download the Drive file.')
            if meta.get('mimeType') not in ('video/mp4', 'video/quicktime'):
                raise TransferError('Drive file is not an MP4/MOV video.')
            if int(meta.get('size', 0)) > self.max_bytes:
                raise TransferError('Drive video exceeds the configured byte limit.')
            target = 'https://www.googleapis.com/drive/v3/files/'+fid+'?alt=media'
        else:
            target = 'https://drive.usercontent.google.com/download?' + urlencode({'id':fid, 'export':'download', **({'resourcekey':key} if key else {})})
        return self.download(target, destination, DRIVE_HOSTS, headers, fid)
    def download(self, url, destination, allowed, headers=None, drive_file_id=None):
        dst = Path(destination); part = dst.with_suffix('.part')
        headers = dict(headers or {}); original_host = urlsplit(url).hostname
        try:
            for attempt in range(6):
                self.permit(url, allowed)
                # Never forward the OAuth bearer credential to a different origin.
                request_headers = headers if urlsplit(url).hostname == original_host else {}
                with self.client.stream('GET', url, headers=request_headers) as r:
                    if r.status_code in (301,302,303,307,308):
                        target = r.headers.get('location', '')
                        self.permit(target, allowed); url = target; continue
                    if r.status_code != 200:
                        raise TransferError(f'Video download failed (HTTP {r.status_code}); check link expiry and access permission.')
                    if int(r.headers.get('content-length', '0')) > self.max_bytes:
                        raise TransferError('Video exceeds configured download byte limit.')
                    if 'text/html' in r.headers.get('content-type', '').lower():
                        # Google large-file virus-scan confirmation. Never follow login pages.
                        html = bytearray()
                        for data in r.iter_bytes(65536):
                            html.extend(data)
                            if len(html)>256*1024: raise TransferError('Drive returned an oversized HTML page, not a video.')
                        form = DownloadForm(); form.feed(html.decode('utf-8', errors='replace'))
                        if attempt or not drive_file_id or not form.action or form.fields.get('id') != drive_file_id:
                            raise TransferError('Drive requires authentication or download permission. Provide an authorized OAuth token; do not make the file public.')
                        self.permit(form.action, {'drive.usercontent.google.com'})
                        if urlsplit(form.action).query: raise TransferError('Unexpected Drive confirmation action.')
                        permitted = {'id','export','confirm','uuid','resourcekey'}
                        if set(form.fields) - permitted: raise TransferError('Unsupported Drive confirmation fields.')
                        url = form.action + '?' + urlencode(form.fields); continue
                    if shutil.disk_usage(dst.parent).free < 128*1024**2:
                        raise TransferError('Insufficient workspace disk space.')
                    digest = hashlib.sha256(); count = 0
                    with part.open('xb') as output:
                        for data in r.iter_bytes(1024**2):
                            count += len(data)
                            if count > self.max_bytes: raise TransferError('Video exceeds byte limit during streaming.')
                            if shutil.disk_usage(dst.parent).free < len(data)+64*1024**2: raise TransferError('Workspace disk exhausted during download.')
                            output.write(data); digest.update(data)
                    expected = r.headers.get('content-length')
                    if expected and count != int(expected): raise TransferError('Truncated video download.')
                    if not count: raise TransferError('Empty video download.')
                    part.replace(dst)
                    return {'bytes':count, 'sha256':digest.hexdigest(), 'transport':'https-stream'}
            raise TransferError('Too many storage redirects or confirmation requests.')
        except httpx.HTTPError:
            raise TransferError('Video transfer network/TLS failure; URL and credentials omitted.') from None
        finally:
            part.unlink(missing_ok=True)
    def upload_drive(self, video, token, folder_id):
        if not token or not re.fullmatch(r'[A-Za-z0-9_-]{10,200}', folder_id or ''):
            raise TransferError('Drive upload requires a real OAuth token and destination folder ID.')
        folder = self.get_json('https://www.googleapis.com/drive/v3/files/'+folder_id+'?fields=id,mimeType,capabilities,permissions', {'Authorization':'Bearer '+token})
        if folder.get('mimeType') != 'application/vnd.google-apps.folder' or folder.get('capabilities',{}).get('canAddChildren') is not True:
            raise TransferError('Destination is not a writable authorized Drive folder.')
        if 'permissions' not in folder or any(p.get('type') == 'anyone' for p in folder['permissions']):
            raise TransferError('Cannot confirm private destination folder permissions; public-folder upload is refused.')
        url = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&fields=id,name,webViewLink'
        self.permit(url, {'www.googleapis.com'})
        video = Path(video); size = video.stat().st_size
        headers = {'Authorization':'Bearer '+token, 'X-Upload-Content-Type':'video/mp4', 'X-Upload-Content-Length':str(size)}
        try:
            r = self.client.post(url, headers=headers, json={'name':video.name,'parents':[folder_id]})
            if r.status_code != 200: raise TransferError(f'Drive upload initialization denied (HTTP {r.status_code}).')
            session = r.headers.get('location',''); self.permit(session, {'www.googleapis.com'})
            offset = 0; failures = 0
            with video.open('rb') as f:
                while offset < size:
                    f.seek(offset); data = f.read(CHUNK)
                    try:
                        r = self.client.put(session, headers={'Authorization':'Bearer '+token,'Content-Type':'video/mp4',
                              'Content-Range':f'bytes {offset}-{offset+len(data)-1}/{size}'}, content=data)
                        if r.status_code in (200,201):
                            result = r.json()
                            if not result.get('id'): raise TransferError('Drive did not return an uploaded file ID.')
                            return result  # no permissions.create or sharing mutation
                        if r.status_code != 308: raise httpx.RequestError('chunk transfer failed')
                        m = re.fullmatch(r'bytes=0-(\d+)',r.headers.get('range',''))
                        next_offset = int(m[1])+1 if m else 0
                        if not offset < next_offset <= size: raise TransferError('Invalid Drive resumable offset.')
                        offset = next_offset; failures = 0
                    except httpx.HTTPError:
                        failures += 1
                        if failures > 3: raise TransferError('Drive upload interrupted; private resumable session not disclosed.') from None
                        status = self.client.put(session, headers={'Authorization':'Bearer '+token,'Content-Range':f'bytes */{size}'},content=b'')
                        if status.status_code in (200,201):
                            result=status.json()
                            if not result.get('id'):raise TransferError('Drive did not return an uploaded file ID.')
                            return result
                        if status.status_code != 308: raise TransferError('Cannot resume Drive upload.')
                        m = re.fullmatch(r'bytes=0-(\d+)',status.headers.get('range',''))
                        offset = int(m[1])+1 if m else 0
                        if not 0 <= offset < size: raise TransferError('Invalid Drive recovery offset.')
        except httpx.HTTPError:
            raise TransferError('Drive upload network/TLS failure; session URL and credentials omitted.') from None
        raise TransferError('Drive upload did not complete.')
