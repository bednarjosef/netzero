import uvicorn, json
import asyncio

from contextlib import asynccontextmanager
from asyncio import Queue
from threading import Thread, Event
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from utils import ensure_root
from netzero import NetZero


# websockets
main_loop = None
message_queue = Queue()
active_websockets: list[WebSocket] = []


def handle_status(status):
    print(f'STATUS: {status}')

    if main_loop and main_loop.is_running():
        msg = json.dumps({'type': 'status', 'status': status})
        asyncio.run_coroutine_threadsafe(message_queue.put(msg), main_loop)

def handle_data(data):
    print(f'DATA: {data}')

    if main_loop and main_loop.is_running():
        msg = json.dumps({'type': 'data', 'data': data})
        asyncio.run_coroutine_threadsafe(message_queue.put(msg), main_loop)

async def broadcast_messages():
    while True:
        msg = await message_queue.get()
        for ws in list(active_websockets):
            try:
                await(ws.send_text(msg))
            except Exception as e:
                print(f'Websocket error during broadcast: {e}')
                active_websockets.remove(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    broadcaster_task = asyncio.create_task(broadcast_messages())
    yield
    broadcaster_task.cancel()


app = FastAPI(title='NetZero API', lifespan=lifespan)
netzero = NetZero(status_callback=handle_status, data_callback=handle_data)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket('/ws/v1/stream')
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


@app.get('/')
def serve_dashboard():
    return FileResponse('index.html')


# REST
@app.get('/api/v1/ping')
def health_check():
    return {'status': 'alive'}

@app.get('/api/v1/interfaces')
def interfaces():
    return { 'data': netzero.get_interfaces() }

@app.get('/api/v1/interface')
def current_interface():
    return { 'data': netzero.get_interface() }

@app.post('/api/v1/scan/start')
def start_scan():
    if not netzero.is_idle():
        raise HTTPException(status_code=400, detail='NetZero already executing a task.')
    
    netzero.scan_networks()
    return { 'message': 'Scan started.' }
    

@app.post('/api/v1/scan/stop')
def stop_scan():
    if not netzero.is_current_task('scanning'):
        return { 'message': 'NetZero is not currently scanning.' }
    
    netzero.stop_current_task()
    return { 'message': 'Scanning stopped succesfully.' }


if __name__ == '__main__':
    ensure_root()
    uvicorn.run(app, host='0.0.0.0', port=80)
