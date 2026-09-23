#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import platform
import psutil

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            mem = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=1)
            disk = psutil.disk_usage('/')
            
            data = {
                'hostname': os.environ.get('HOSTNAME', 'unknown'),
                'python_version': platform.python_version(),
                'cpu_percent': cpu,
                'memory_percent': mem.percent,
                'memory_total_mb': round(mem.total / (1024**2), 2),
                'disk_percent': disk.percent,
                'disk_total_gb': round(disk.total / (1024**3), 2)
            }
            
            self.wfile.write(json.dumps(data, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f'Starting server on port {port}')
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()