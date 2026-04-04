import re

with open('pipeline/dashboard.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Remove duplicate lines of code in GET
# Since it's corrupted with duplicated /api/templates and /api/gallery in GET, let's strip them all out, then re-insert cleanly.

# Find the start of do_GET
get_start = text.find('    def do_GET(self) -> None:')
post_start = text.find('    def do_POST(self) -> None:')

if get_start != -1 and post_start != -1:
    get_body = text[get_start:post_start]
    
    # We will rewrite get_body to remove duplicates and bad methods
    # It has: /, /api/system, /api/status, /api/logs, /api/history, /api/templates, etc
    clean_get = '''    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/":
            body = get_html()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/system":
            self._send_json(get_system_status())
            return

        if parsed.path == "/api/status":
            self._send_json(self.runtime.get_status())
            return

        if parsed.path == "/api/logs":
            since = _safe_int((query.get("since") or [0])[0], 0, min_value=0)
            limit = _safe_int((query.get("limit") or [200])[0], 200, min_value=1, max_value=800)
            run_id = (query.get("run_id") or [None])[0]
            self._send_json(self.runtime.get_logs(since=since, limit=limit, run_id=run_id))
            return

        if parsed.path == "/api/history":
            limit = _safe_int((query.get("limit") or [20])[0], 20, min_value=1, max_value=200)
            self._send_json(self.runtime.get_history(limit=limit))
            return

        if parsed.path == "/api/modules/jobs":
            limit = _safe_int((query.get("limit") or [40])[0], 40, min_value=1, max_value=400)
            self._send_json(self.runtime.list_module_jobs(limit=limit))
            return

        if parsed.path == "/api/modules/job-detail":
            job_id = (query.get("job_id") or [""])[0]
            log_limit = _safe_int((query.get("log_limit") or [300])[0], 300, min_value=1, max_value=1500)
            event_limit = _safe_int((query.get("event_limit") or [200])[0], 200, min_value=1, max_value=1200)
            self._send_json(self.runtime.get_module_job_detail(job_id=job_id, log_limit=log_limit, event_limit=event_limit))
            return

        if parsed.path == "/api/images/items":
            story_root_hint = (query.get("story_root") or [None])[0]
            limit = _safe_int((query.get("limit") or [200])[0], 200, min_value=1, max_value=800)
            self._send_json(self.runtime.list_image_items(story_root_hint=story_root_hint, limit=limit))
            return

        if parsed.path == "/api/images/file":
            raw_path = (query.get("path") or [""])[0]
            file_path = self.runtime._safe_path_under_root(raw_path)
            if not file_path or not file_path.exists() or not file_path.is_file():
                self._send_json({"ok": False, "error": "file not found"}, status=404)
                return
            mtype, _ = mimetypes.guess_type(str(file_path))
            try:
                body = file_path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mtype or "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
                return

        if parsed.path == "/api/templates":
            import json
            from pathlib import Path
            p = Path("runs/prompt_templates.json")
            data = []
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    pass
            self._send_json(data)
            return

        if parsed.path == "/api/gallery":
            import json, os
            from pathlib import Path
            galleries = []
            if Path("output").exists():
                for d in Path("output").iterdir():
                    if d.is_dir() and d.name != "暫存":
                        for story in d.iterdir():
                            if story.is_dir() and (story / "story.json").exists():
                                info = {}
                                try:
                                    with open(story/"story.json", "r", encoding="utf-8") as f:
                                        info = json.load(f)
                                except: pass
                                
                                # try find cover
                                cover_path = None
                                main_cover = story / "image/main/book_cover.png"
                                if main_cover.exists(): cover_path = str(main_cover.as_posix())
                                
                                galleries.append({
                                    "title": info.get("title", story.name),
                                    "category": d.name,
                                    "path": str(story.as_posix()),
                                    "modified": str(os.path.getmtime(story)),
                                    "cover": cover_path
                                })
            galleries.sort(key=lambda x: float(x["modified"]), reverse=True)
            self._send_json({"images": galleries})
            return

        self._send_json({"ok": False, "error": "not found"}, status=404)

'''
    
    text = text[:get_start] + clean_get + text[post_start:]

# 2. Add /api/templates/save to do_POST
post_marker = "if parsed.path == \"/api/start\":"
save_post = '''if parsed.path == "/api/templates/save":
            payload = self._read_json_body()
            name = payload.get("name")
            prompt = payload.get("prompt")
            neg = payload.get("negative_prompt", "")
            import json
            from pathlib import Path
            p = Path("runs/prompt_templates.json")
            data = []
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    pass
            data.append({"name": name, "prompt": prompt, "negative_prompt": neg, "id": str(len(data))})
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._send_json({"ok": True, "templates": data})
            return

        '''

if text.find('/api/templates/save') == -1 or text.find('/api/templates/save') < post_start:
    text = text.replace(post_marker, save_post + post_marker)


with open('pipeline/dashboard.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Dashboard rewrite complete!")

