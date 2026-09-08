import asyncio
import socket
import uuid
import psutil
import platform
import websockets
import json
import datetime

SERVER_IP = "10.158.60.63" 
SERVER_PORT = 8000
SYSTEM_INFO_REFRESH_SECONDS = 30

CLIENT_ID = str(uuid.uuid4())[:8]
HOSTNAME = socket.gethostname()

def get_system_info():
    uname = platform.uname()
    
    # Boot time
    boot_time_timestamp = psutil.boot_time()
    bt = datetime.datetime.fromtimestamp(boot_time_timestamp)
    boot_time = f"{bt.year}/{bt.month}/{bt.day} {bt.hour}:{bt.minute}:{bt.second}"
    
    # CPU
    try:
        cpu_freq = psutil.cpu_freq()
        max_freq = f"{cpu_freq.max:.2f}Mhz" if cpu_freq else "Unknown"
    except Exception:
        max_freq = "Unknown"
    
    # Memory
    svmem = psutil.virtual_memory()
    total_ram = f"{svmem.total / (1024 ** 3):.2f}GB"
    
    # Disk
    partitions = psutil.disk_partitions()
    disks = []
    for partition in partitions:
        try:
            partition_usage = psutil.disk_usage(partition.mountpoint)
            disks.append({
                "device": partition.device,
                "mountpoint": partition.mountpoint,
                "fstype": partition.fstype,
                "total": f"{partition_usage.total / (1024**3):.2f}GB",
                "used": f"{partition_usage.used / (1024**3):.2f}GB",
                "free": f"{partition_usage.free / (1024**3):.2f}GB",
                "percent": f"{partition_usage.percent}%"
            })
        except PermissionError:
            continue
            
    # Network
    if_addrs = psutil.net_if_addrs()
    networks = {}
    for interface_name, interface_addresses in if_addrs.items():
        networks[interface_name] = []
        for address in interface_addresses:
            family_name = str(address.family)
            if 'AF_INET' in family_name and 'AF_INET6' not in family_name:
                networks[interface_name].append({"IP": address.address})
            elif 'AF_PACKET' in family_name or 'AF_LINK' in family_name:
                networks[interface_name].append({"MAC": address.address})

    return {
        "os": f"{uname.system} {uname.release}",
        "node_name": uname.node,
        "version": uname.version,
        "machine": uname.machine,
        "processor": uname.processor,
        "boot_time": boot_time,
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "cpu_cores_total": psutil.cpu_count(logical=True),
        "cpu_max_freq": max_freq,
        "total_ram": total_ram,
        "disks": disks,
        "networks": networks
    }

async def connect_to_server():
    uri = f"ws://{SERVER_IP}:{SERVER_PORT}/ws"

    while True:
        try:
            print(f"Connecting to {uri}...")
            async with websockets.connect(uri) as websocket:
                print("Connected to server!")

                sys_info = get_system_info()
                last_system_info_sent = datetime.datetime.now()

                await websocket.send(json.dumps({
                    "type": "handshake",
                    "id": CLIENT_ID,
                    "hostname": HOSTNAME,
                    "system_info": sys_info
                }))

                while True:
                    cpu = psutil.cpu_percent(interval=1)
                    ram = psutil.virtual_memory().percent
                    
                    # Net IO
                    net_io = psutil.net_io_counters()
                    bytes_sent = f"{net_io.bytes_sent / (1024**2):.2f}MB"
                    bytes_recv = f"{net_io.bytes_recv / (1024**2):.2f}MB"
                    
                    # Disk IO
                    disk_io = psutil.disk_io_counters()
                    if disk_io:
                        read_bytes = f"{disk_io.read_bytes / (1024**2):.2f}MB"
                        write_bytes = f"{disk_io.write_bytes / (1024**2):.2f}MB"
                    else:
                        read_bytes = "0MB"
                        write_bytes = "0MB"

                    data = {
                        "type": "status",
                        "hostname": HOSTNAME,
                        "cpu": cpu,
                        "ram": ram,
                        "net_sent": bytes_sent,
                        "net_recv": bytes_recv,
                        "disk_read": read_bytes,
                        "disk_write": write_bytes
                    }

                    now = datetime.datetime.now()
                    elapsed = (now - last_system_info_sent).total_seconds()
                    if elapsed >= SYSTEM_INFO_REFRESH_SECONDS:
                        sys_info = get_system_info()
                        data["system_info"] = sys_info
                        last_system_info_sent = now

                    await websocket.send(json.dumps(data))
                    await asyncio.sleep(2)

        except Exception as e:
            print("Connection failed:", e)
            print("Retrying in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(connect_to_server())
