import http.server
import socketserver
import os

PORT = 8080
FILE_PATH = 'poly.db.gz'

class AutoDownloadHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/' + FILE_PATH:
            if os.path.exists(FILE_PATH):
                self.send_response(200)
                self.send_header('Content-Type', 'application/gzip')
                self.send_header('Content-Disposition', f'attachment; filename="{FILE_PATH}"')
                self.send_header('Content-Length', str(os.path.getsize(FILE_PATH)))
                self.end_headers()
                with open(FILE_PATH, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "File not found")
        else:
            self.send_error(404, "Not found")

print(f"Starting auto-download server on port {PORT}...")
with socketserver.TCPServer(("", PORT), AutoDownloadHandler) as httpd:
    httpd.serve_forever()
