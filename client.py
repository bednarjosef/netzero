import asyncio
import websockets
import requests
import threading
import json
import sys

PI_IP = '172.16.0.1'
PORT = 80

HTTP_URL = f"http://{PI_IP}:{PORT}/api/v1"
WS_URL = f"ws://{PI_IP}:{PORT}/ws/v1/stream"


# listener
async def listen_to_websocket():
    try:
        async with websockets.connect(WS_URL) as ws:
            print(f"\n[+] Connected to live data stream at {WS_URL}")
            while True:
                raw_msg = await ws.recv()
                try:
                    data = json.loads(raw_msg)
                    if data.get("type") == "status":
                        print(f"[STATUS] {data['status']}")
                    elif data.get("type") == "data":
                        print(f"[DATA] {data['data']}")
                except json.JSONDecodeError:
                    print(f"\n[RAW] {raw_msg}")
                    
    except Exception as e:
        print(f"\n[-] WebSocket connection failed: {e}")
        print("    Make sure the Pi server is running and the IP is correct.")

def start_ws_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(listen_to_websocket())


def print_menu():
    print("\n" + "="*30)
    print("      NETZERO TEST CLIENT      ")
    print("="*30)
    print("[1] Ping Server")
    print("[2] Start Scan")
    print("[3] Stop Scan")
    print("[4] Exit")
    print("="*30)

def main():
    ws_thread = threading.Thread(target=start_ws_thread, daemon=True)
    ws_thread.start()

    while True:
        print_menu()
        choice = input("Enter command: ")

        try:
            if choice == '1':
                res = requests.get(f"{HTTP_URL}/ping")
                print(f"Server response: {res.json()}")

            elif choice == '2':
                res = requests.post(f"{HTTP_URL}/scan/start")
                print(f"Server response: {res.json()}")

            elif choice == '3':
                res = requests.post(f"{HTTP_URL}/scan/stop")
                print(f"Server response: {res.json()}")

            elif choice == '4':
                print("Exiting...")
                sys.exit(0)
            else:
                print("Invalid choice.")
                
        except requests.exceptions.ConnectionError:
            print("[-] HTTP Request Failed: Could not connect to the Pi.")

if __name__ == "__main__":
    main()