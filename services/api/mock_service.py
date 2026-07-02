import os
import http.server
import socketserver
import time


class MockHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"healthy"}')


def run_server(port):
    with socketserver.TCPServer(("", port), MockHandler) as httpd:
        print(f"Serving on port {port}")
        httpd.serve_forever()


if __name__ == "__main__":
    port_str = os.environ.get("PORT")
    if port_str:
        run_server(int(port_str))
    else:
        print("Mock service running...")
        while True:
            time.sleep(3600)
