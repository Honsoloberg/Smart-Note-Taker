#define bluetooth services for file interaction
# 
#SERVICE 1: basic file management
# - send a list of files to the phone, file1\nfile2\nfile3\n...
# - accept filename from phone, delete the file from the sd
#
#SERVICE 2: stream audio
# - accept filename from phone
# - stream requested file in chunks, sent using ble notify (not read/write)
#
#SERVICE 3: transfer audio
# - accept filename from phone, set global variable and use wifi GET method to transfer file
#
#
#bluetooth code
import bluetooth
import asyncio
import aioble
import os
import sdcard
from machine import Pin, SPI, I2S
import uos
import uasyncio
import time
import urandom
#add wifi code
import network
import socket
import _thread
import struct


#set up sd card
sd_spi= SPI(
    0,
    baudrate=1000000,
    polarity=0,
    phase=0,
    sck=Pin(18),
    mosi=Pin(19),
    miso=Pin(16)
)
sd_cs = Pin(17, Pin.OUT)

sd = sdcard.SDCard(sd_spi, sd_cs)
vfs = uos.VfsFat(sd)
uos.mount(vfs,"/sd")
print("SD mounted")


# set up VS1053 for Ogg Encoding

# pins for VS1053
XCS = Pin(9, Pin.OUT, value=1) #control chip select
XDCS = Pin(7, Pin.OUT, value=1) #data chip select
DREQ = Pin(6, Pin.IN) #data request
RST = Pin(5, Pin.OUT, value=1) #reset

# SPI for VS1053
spi = SPI(
    1,
    baudrate=1000000,
    polarity=0,
    phase=0,
    sck=Pin(14),
    mosi=Pin(15),
    miso=Pin(8)
)

# functions for VS1053
def sci_write(addr, value):
    while not DREQ.value():
        pass
    XCS.value(0)
    spi.write(bytearray([0x02, addr, value >> 8, value & 0xFF]))
    XCS.value(1)

def sci_read(addr):
    while not DREQ.value():
        pass
    XCS.value(0)
    spi.write(bytearray([0x03, addr]))
    result = spi.read(2)
    XCS.value(1)
    return (result[0] << 8) | result[1]

def plugin_img_loader(filename):
    with open(filename, "rb") as f:
        #check header "P&H"
        if f.read(3) != b"P&H":
            return 0xFFFF
        offsets = [0x8000, 0x0000, 0x4000] # I, X, Y memory
        
        while True:
            type_byte = f.read(1)
            if not type_byte:
                return 0xFFFF
            
            rtype = type_byte[0]
            if rtype >= 4:
                return 0xFFFF
            
            #read length (even number)
            len_hi = f.read(1)[0]
            len_lo = f.read(1)[0] & 0xFE
            length = (len_hi << 8) | len_lo
            
            #read address
            addr_hi = f.read(1)[0]
            addr_lo = f.read(1)[0]
            addr = (addr_hi << 8) | addr_lo
            
            #execute record, return start address
            if rtype == 3:
                return addr
            
            #set WRAMADDR = addr + offset
            sci_write(0x07, addr + offsets[rtype])
            
            #write data words
            for _ in range(length // 2):
                hi = f.read(1)[0]
                lo = f.read(1)[0]
                data = (hi << 8) | lo
                sci_write(0x06, data)

                   
# function to initialize VS1053 with Ogg encoding
def init_vs1053():
    print("Resetting VS1053...")
    
    #hardware reset
    RST.value(0)
    time.sleep(0.1)
    RST.value(1)
    time.sleep(0.1)
    
    #1. set CLOCKF = 0xC000 (4.5x clock) required for ogg encoder
    sci_write(0x03, 0xC000)
    print("step 1 clock:", hex(sci_read(0x03)))
    while not DREQ.value():
        pass
    
    #2. clear the bass sci_bass = 0
    sci_write(0x02, 0)
    print("step 2 bass:", hex(sci_read(0x02)))
    
    #3. soft reset, mode = SM_SDINEW | SM_RESET
    mode = (1 << 11) | (1 <<2)  #setting it to 8 ******
    sci_write(0x00, mode)

    #wait for reset to complete
    while not DREQ.value():
        pass
    print("step 3 mode:", hex(sci_read(0x00)))
    print(hex(mode))
    
    #4. disable interrupts except for sci
    sci_write(0x07, 0xC01A) #WRAMADDR = VS1053_INT_ENABLE
    sci_write(0x06, 0x0002) #WRAM = 2 (sci interrupt only)
    print("step 4 wram:", hex(sci_read(0x06)))
    print("wramaddr:", hex(sci_read(0x07)))
    
    #5. load the ogg vorbis encoder plugin
    print("Loading Ogg vorbis encoder image...")
    plugin_start = plugin_img_loader("venc16k1q05.img")
    print("Plugin start address:", hex(plugin_start))
    
    if plugin_start == 0xFFFF:
        print("Plugin load failed!")
        return
    
    #6. set sci_mode after plugin load (critical step)
    #     mode = SM_SDINEW | SM_ADPCM (no line1)
    mode = (1 << 11) | (1 << 12) | (1<<14)
    sci_write(0x00, mode)
    print("step 5 mode:", hex(sci_read(0x00)))
    print(hex(mode))
    #7. set AICTRL registers before starting encoder
    sci_write(0x0D, 1024) #aictrl1 = 0 (agc enabled)
    sci_write(0x0E, 4096) #aictrl2 = max agc gain
    sci_write(0x0F, 0) #aictrl3 = 0
    sci_write(0x0C, 0)
    
    #8. start encoder by writing start address to AIADDR
    sci_write(0x0A, plugin_start)
    #wait for encoder to initialize
    time.sleep(0.05)
    #wait for reset to complete
    while not DREQ.value():
        pass
    time.sleep(1)
    #9. dump registers for debugging
    #check register contents
    print("SCI_MODE:", hex(sci_read(0x00)))
    print("clockf:", hex(sci_read(0x03)))
    print("SCI_STATUS:", hex(sci_read(0x01)))
    print("SCI_AICTRL0:",sci_read(0x0C))
    print("SCI_AICTRL1:", sci_read(0x0D))
    print("SCI_AICTRL2:", sci_read(0x0E))
    print("SCI_AICTRL3:", sci_read(0x0F))

#button to start/stop recording
button = Pin(4, Pin.IN, Pin.PULL_UP)
led = Pin(3, Pin.OUT)
led.value(0)
buttonState = False
last = 1 #previous button state

#global stop flag
record_stop_requested = False
recording_done = False
#record audio, send to VS1053, read ogg output into file
def record_ogg(filename="recording.ogg"):
    global record_stop_requested, recording_done
    c=0;
    last = 1

    print("Starting recording...")
    led.value(1)
    
#     pcm_buf = bytearray(512) #buffer to hold I2S samples
    try:
        with open("/sd/" + filename, "wb") as f:
    #         start = time.time()
            state = 0
            
            while state < 3:
                #if stop was requested and not yet in stop sequence
                #stop condition: check if button was pressed
                if record_stop_requested and state == 0:
                    state = 1
                    sci_write(0x0F, 1) #request stop
                    
                    print("Requested to stop: step 1")
                    time.sleep(2)
                    
    #             if last == 1 and button.value() == 0:
    #                 buttonState = not buttonState
    #                 time.sleep(0.02)
    #                 while button.value() ==0:
    #                     pass
    #                 
    #             last = button.value()
    #             time.sleep(0.01)
    #             #stop condition
    #             #print(c)
    #             #if(time.time() - start) > duration and state == 0:
    #             if buttonState == 0 and state == 0:
    #             #if c > 10000 and state == 0:
    #                 #print("B1 start")
    #                 state = 1
    #                 sci_write(0x0F, 1) #AICTRL = 1, request stop
    #                 print("requested to stop: step 1");
    #                 time.sleep(2);
        
                #words waiting
                wordsWaiting = sci_read(0x09) #sci_hdat1
                #print(wordsWaiting);
                #check if encoder has finished
                if state == 1 and (sci_read(0x0F) & (1 << 1)):
                    #print("B3 start")
                    state = 2
                    wordsWaiting = sci_read(0x09)
                    #print("requested to stop: step 2");
                
                #read blocks
                #print(wordsWaiting)
                while wordsWaiting >= (256 if state < 1 else 1):
                    #print("B4 start")
                    wordsToRead = min(wordsWaiting, 256)
                    wordsWaiting -= wordsToRead
                    
                    #if last block, leave last word for special handling
                    if state == 2 and wordsWaiting != 0:
                        wordsToRead -= 1
                    
                    #read wordsToRead words
                    for _ in range(wordsToRead):
                        #print("B5 start")
                        w = sci_read(0x08)
                        c+=1;
                        #if(c<10):
                            #print(hex(w))
                        f.write(bytes([(w >> 8) & 0xFF, w & 0xFF]))
                        
                    #if last block
                    if wordsToRead < 256:
                        #print("B7 start")
                        lastWord = sci_read(0x08)
                        state = 3
                        print("requested to stop: step 3");
                        
                        #always write high byte
                        f.write(bytes([(lastWord >> 8) & 0xFF]))
                        
                        #check AICTRL3 bit 2
                        sci_read(0x0F)
                        if not (sci_read(0x0F) & (1 << 2)):
                            f.write(bytes([lastWord & 0xFF]))
                #print(state);
    finally:
        print("Recording Complete.")
        led.value(0)
        print(c)
        recording_done = True
   
def delete_file(filename):
    try:
        uos.stat("/sd/" + filename)#check status of file
        uos.remove("/sd/" + filename)
        print("file has been deleted")
    except OSError as e:
        print("file not found")

#function to generate unique filename
def generate_filename(extension="ogg"):
#     t = time.localtime()
#     #format as YYYYMMDD_HHMM.ogg
#     filename = "{:04d}-{:02d}-{:02d}_{:02d}_{:02d}.{}".format(
#         t[0], t[1], t[2], t[3], t[4], extension
#     )
    n=1
    while True:
        filename = f"Audio{n}.ogg"
        if filename not in os.listdir("/sd/"):
            return filename
        n += 1

async def button_record_task():
    global buttonState, last, recording_active, record_stop_requested, recording_done
    #variables related to bluetooth shutdown
    global current_connection, peripheral_task_handle
    
    while True:
#         #Toggle button state
#         if last == 1 and button.value() == 0:
#             buttonState = not buttonState
#             time.sleep(0.02)
#             while button.value() == 0:
#                 await asyncio.sleep_ms(5)
#         last = button.value()
        
        #check button press
        #check the recording_active flag, and the button value itself as an edge case
        if last == 1 and button.value() == 0:
            #debounce
            time.sleep(0.02)
            while button.value() == 0:
                await asyncio.sleep_ms(5)
                
            if not recording_active:
                #start recording
                print("Recording starting...")
                recording_active = True
                record_stop_requested = False
                recording_done = False
                
                #step 1: stop BLE/sd tasks
                await stop_ble_sd_tasks()
                #disable BLE gap_peripheral (reject connections)
#                 try:
#                     ble.config(gap_peripheral = False)
#                     print("BLE peripheral role disabled")
#                 except Exception as e:
#                     print("Error disabling peripheral role:", e)
                #hard-disable BLE radio
#                 try:
#                     ble_radio.active(False)
#                     print("BLE radio OFF")
#                 except Exception as e:
#                     print("Error disabling BLE:", e)
                #step 2: stop wifi
                try:
                    sta.disconnect()
                except:
                    pass
                sta.active(False)
                #step 3: init codec + filename
                filename = generate_filename()
                init_vs1053()
                #step 4: start recording thread
                import _thread
                _thread.start_new_thread(record_ogg, (filename,))
            else:
                #stop request
                print("stop requested by button")
                record_stop_requested = True
        last = button.value()
        
        #if recording is active, wait for thread to finish
        if recording_active and recording_done:
            print("Recording finished, resuming system")
            #restart wifi
            try:
                sta.active(True)
            except:
                pass
            
            #re-enable BLE gap peripheral role (allow connections)
#             try:
#                 ble.config(gap_peripheral=True)
#                 print("BLE peripheral role enabled")
#             except Exception as e:
#                 print("Error enabling peripheral role:", e)
            #re-enable BLE radio
#             try:
#                 ble_radio.active(True)
#                 aioble.register_services(service1, service2, service3)
#                 print("BLE radio ON")
#             except Exception as e:
#                 print("Error enabling BLE:", e)
                
            #restart BLE/SD tasks
            await start_ble_sd_tasks()
            
            recording_active = False
            record_stop_requested = False
            recording_done = False
            
        await asyncio.sleep_ms(10)
#         
#             if not recording_active:
#                 #start recording
#                 buttonState = True
#             else:
#                 #request stop
#                 record_stop_requested = True
#                 buttonState = False
#             time.sleep(0.02)
#             while button.value() == 0:
#                 await asyncio.sleep_ms(5)
#         last = button.value()
#             
#         
#         #start recording
#         if buttonState and not recording_active:
#             recording_active = True
#             record_stop_requested = False
#             print("Recording starting...")
#             
#             #step 1: kill any active BLE connections
#             try:
#                 if current_connection is not None:
#                     await current_connection.disconnect()
#             except Exception as e:
#                 print("Error disconnecting BLE:", e)
#             
#             #step 2: cancel peripheral advertising task
#             try:
#                 if peripheral_task_handle is not None:
#                     peripheral_task_handle.cancel()
#             except Exception as e:
#                 print("Error cancelling peripheral task:", e)
#             
#             #step 3: stop wifi
#             try:
#                 sta.disconnect()
#                 sta.active(False)
#             except:
#                 pass
#             
#             #stop BLE advertising and disconnect
#             try:
#                 ble.gap_advertise(None)
#                 ble.disconnect_all()
#             except:
#                 pass
#             #stop wifi
#             try:
#                 sta.disconnect()
#                 sta.active(False)
#             except:
#                 pass
            
#             filename = generate_filename()
#             init_vs1053()
#             
#             #Run the blocking recorder in a thread
#             import _thread
#             _thread.start_new_thread(record_ogg, (filename,))
#             #_thread.start_new_thread(record_ogg, (file_name, True))
#             
#             #wait until recording stops (user presses button again)
#             while buttonState:
#                 await asyncio.sleep_ms(50)
#             
#             print("Recording finished. Resuming system")
#             
#             #re-enable BLE
#             try:
#                 ble.active(True)
#                 start_ble_advertising()
#             except:
#                 pass
#             #re-enable wifi
#             try:
#                 sta.active(True)
#             except:
#                 pass
            #re-enable wifi
#             try:
#                 sta.active(True)
#             except:
#                 pass
#             
#             #restart peripheral task
#             try:
#                 peripheral_task_handle = asyncio.create_task(peripheral_task())
#             except Exception as e:
#                 print("Error restarting peripheral task:", e)
#             
#             
#             recording_active = False
#             record_stop_requested = False
#         await asyncio.sleep_ms(10)

     
#
#BLUETOOTH CODE
#

#UUIDs for services and characteristics
#0xFFF_ are vendor-specific service UUIDs, safe for custom services

#service 1 for file list, delete
SERVICE1_UUID = bluetooth.UUID(0xFFF8)
FILELIST_UUID = bluetooth.UUID(0xFFF9) #read/notify
DELETE_UUID = bluetooth.UUID(0xFFFA) #write

#service 2 for requesting and streaming audio from file
SERVICE2_UUID = bluetooth.UUID(0xFFF3) #vendor-specific service UUIDs, safe for custom services
FILE_SELECT_UUID = bluetooth.UUID(0xFFF4)
AUDIO_STREAM_UUID = bluetooth.UUID(0xFFF5)

#service 3 for requesting and transfering a file over wifi
SERVICE3_UUID = bluetooth.UUID(0xFFF6)
FILE_TRANSFER_SELECT_UUID = bluetooth.UUID(0xFFF7)

#register services on GATT server
#service 1
service1 = aioble.Service(SERVICE1_UUID)
filelist_char = aioble.Characteristic(
    service1,
    FILELIST_UUID,
    read=True,
    notify=True,
    write=True,
    )

delete_char = aioble.Characteristic(
    service1,
    DELETE_UUID,
    write=True,
    write_no_response=True,
    )

#service 2
service2 = aioble.Service(SERVICE2_UUID)
file_select_char = aioble.Characteristic(
    service2,
    FILE_SELECT_UUID,
    write=True,
    write_no_response=True,
    )

audio_stream_char = aioble.Characteristic(
    service2,
    AUDIO_STREAM_UUID,
    read=True,
    notify=True,
    )

#service 3
service3 = aioble.Service(SERVICE3_UUID)
file_transfer_select_char = aioble.Characteristic(
    service3,
    FILE_TRANSFER_SELECT_UUID,
#     read=True,
    notify=True,
    write=True,
    write_no_response=True,
    )

#create global BLE object
# ble_radio = bluetooth.BLE()
ble = bluetooth.BLE()
#global variables to handle unwanted connections
# _IRQ_CENTRAL_CONNECT = const(1)
# _IRQ_CENTRAL_DISCONNECT = const(2)

#function to help handle unwanted connections during recording
# def ble_irq(event, data):
#     global recording_active
#     
#     if event == _IRQ_CENTRAL_CONNECT:
#         conn_handle, addr_type, addr = data
#         print("Incoming connection:", addr)
#         
#         if recording_active:
#             print("Rejecting connection (recording active)")
#             try:
#                 ble.disconnect(conn_handle)
#             except:
#                 pass
# ble.irq(ble_irq)

#register bluetooth services
aioble.register_services(service1, service2, service3)

# def random_ble_address():
#     #6-byte random static address (MSB must have top two bits =1)
#     addr = bytearray(6)
#     for i in range(6):
#         addr[i] = urandom.getrandbits(8)
#     addr[0] |= 0xC0 #static random address
#     
#     return bytes(addr)


def random_dummy_uuid():
    #generate a random 128 bit UUID
    b = bytes([urandom.getrandbits(8) for _ in range(16)])
    return bluetooth.UUID(b)

def rotated_ble_name():
    #to force the app to rediscover bluetooth GATT
    #cycle through 0-3 trailing spaces, will look the same to users
    global _ble_name_counter
    try:
        _ble_name_counter += 1
    except:
        _ble_name_counter = 1
    
    spaces = " " * (_ble_name_counter % 4)
    return "ResonateController1" + spaces
    

def ble_off():
    try:
        ble.active(False)
        print("BLE OFF")
    except Exception as e:
        print("Error turning BLE off:", e)

_dummy_uuid = random_dummy_uuid()
def ble_on():
    global _dummy_uuid
    try:
        ble.active(True)
        #rotate invisible dummy uuid to force GATT rediscovery
        _dummy_uuid = random_dummy_uuid()
        print("New dummy UUID:", _dummy_uuid)
        
        #rotate whitespace name
        new_name = rotated_ble_name()
        ble.config(gap_name=new_name)
#         new_addr = random_ble_address()
#         ble.config(addr=new_addr, addr_mode=bluetooth.ADDR_MODE_RANDOM)
        print("BLE restarted with new name:", repr(new_name))
        aioble.register_services(service1, service2, service3)
        print("BLE ON + services registered")
    except Exception as e:
        print("Error turning BLE on:", e)
        

#
#FOR FILE TRANSFERS
#

    
#global variable for a file to be transferred
CURRENT_TRANSFER_FILE = None
wifi_server_running = False
wifi_server_shutdown = False
_beacon_task = None

#for faster thread-running http server
_fast_server_running = False
_fast_server_done = False
_fast_server_thread = None

#UDP beacon coroutine
async def udp_beacon_task(port=80, interval=1.5, token="RESO"):
    #broadcast a small UDP packet with the Pico IP and port
    #stop when wifi_server_running becomes False
    
    global _beacon_task
    try:
        #create socket
        #blocking socket used inside uasyncio loop is ok for simple sendto
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(0.5)
    except Exception as e:
        print("Beacon socket error:", e)
        return
    
    try:
        while wifi_server_running:
            try:
                ip = sta.ifconfig()[0]
                msg = "PICO;ip={};port={};token={}".format(ip,port,token)
                
                #broadcast to the local network
                s.sendto(msg.encode(), ("255.255.255.255", 37020))
            except Exception as e:
                #don't crash the loop on transient errors
                print("Beacon send error:", e)
            await asyncio.sleep(interval)
    finally:
        try:
            s.close()
        except:
            pass
        _beacon_task = None
        print("Beacon stopped")
        
#trying to use STA instead of AP
sta = network.WLAN(network.STA_IF)
sta.active(True)
    
def connect_to_phone(ssid, password):
    sta.connect(ssid, password)
    
    for _ in range(20):
        if sta.isconnected():
            print("Connected:", sta.ifconfig())
            return True
        time.sleep(0.5)
        
    print("Failed to connect")
    return False


def start_fast_wifi_transfer(filename):
    global _fast_server_thread
    fast_http_server(filename)
    
def fast_http_server(filename):
    global _fast_server_running, _fast_server_done
    
    path = "/sd/" + filename
    _fast_server_running = True
    _fast_server_done = False
    print("FAST HTTP server starting...")
    
    def server_thread():
        global _fast_server_running, _fast_server_done
        
        try:
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", 80))
            s.listen(1)
            print("FAST HTTP server listening on port 80")

            conn, addr = s.accept()
            print("Client:", addr)
                        
            req = conn.recv(1024)
            print("REQ:", req)
            if b"GET /file" not in req:
                print("FAST SERVER: unexpected request:", req)
                conn.send(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                conn.close()
                s.close()
                _fast_server_done = True
                return
                            
            #send headers in one write
            conn.send(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-type: application/octet-stream\r\n"
                b"Connection: close\r\n\r\n"
                )
                
            CHUNK = 4096
            #stream in small chunks
            with open(path, "rb") as f:
                while True:
                    data = f.read(CHUNK)
                    if not data:
                        break
                    conn.send(data)
                                
            conn.close()
            s.close()
            print("Transfer complete")
        except Exception as e:
            print("FAST HTTP error:", e)
            print("FAST SERVER BIND FAILED - PORT 80 in use")
        
        _fast_server_running = False
        _fast_server_done = True
    
    #start the thread
    _thread.start_new_thread(server_thread, ())


def reset_wifi():
    print("Resetting wifi state...")
    try:
        sta.disconnect()
    except:
        pass
    sta.active(False)
    time.sleep(0.5)


hotspot_ssid = None
hotspot_password = None
transfer_filename = None
#task: wait for filename, open file and transfer over wifi
async def audio_transfer_task():
    global hotspot_ssid, hotspot_password, transfer_filename, CURRENT_TRANSFER_FILE
    global wifi_server_running, _beacon_task
    
    try:
        while True:
            await file_transfer_select_char.written()
            if recording_active:
                await asyncio.sleep_ms(50)
                continue
            
            payload = file_transfer_select_char.read().decode().strip()
            
            #step 1: get SSID
            if payload.startswith("S:"):
                hotspot_ssid = payload[2:]
                print("SSID received:", hotspot_ssid)
                continue
            
            #step 2: get password
            if payload.startswith("P:"):
                hotspot_password = payload[2:]
                print("Password received:", hotspot_password)
                continue
            
            #step 3: get filename
            if payload.startswith("F:"):
                transfer_filename = payload[2:]
                if not transfer_filename.lower().endswith(".ogg"):
                    transfer_filename += ".ogg"
                
                CURRENT_TRANSFER_FILE = transfer_filename
                print("Filename received:", transfer_filename)
                
                #if all three pieces then connect
                if hotspot_ssid and hotspot_password:
                    print("Connecting to hotspot...")
                    if connect_to_phone(hotspot_ssid, hotspot_password):
                        print("Connected! Starting WiFi transfer...")
                        sta.active(True)
                        
                        #start http server and beacon
                        wifi_server_running = True
                        #start beacon task (advertise IP:port to Android
                        #store handle so it can be stopped later
                        _beacon_task = asyncio.create_task(udp_beacon_task(port=80, interval=1.5, token="RESO"))
                       
                        #run http server (this will cancel itself when transfer completes)
                        try:
                            start_fast_wifi_transfer(transfer_filename)
                            
                            #wait for the fast server to finish
                            while not _fast_server_done:
                                await asyncio.sleep_ms(100)
                            print("FAST server reports transfer complete")
                            
                        finally:
                            #stop beacon and server
                            wifi_server_running = False
                            
                            #give beacon loop a moment to exit
                            await asyncio.sleep(0.2)
                            if _beacon_task:
                                #cancel if still running
                                try:
                                    _beacon_task.cancel()
                                except:
                                    pass
                                _beacon_task = None
                        hotspot_ssid = None
                        hotspot_password = None
                        transfer_filename = None
                        reset_wifi()
                    else:
                        print("Failed to connect to hotspot")
                continue
            #unknown message
            print("Unknown BLE payload:", payload)
    except asyncio.CancelledError:
        print("audio_transfer_task cancelled")


#
# FOR SENDING LIST OF FILES
#

#helper function: retrieve list of files
def get_file_list():
    try:
        files = uos.listdir("/sd")
        
        #filter files
        ogg_files = [
            f for f in files
            if f.lower().endswith(".ogg")
        ]
        print("get_file_list() sees:", ogg_files)
        return "\n".join(ogg_files)
    
    except:
        return "SD error"
    
async def update_filelist_for_connection():
    try:
        filelist = get_file_list()
        payload = filelist.encode("utf-8")
        CHUNK = 100 #BLE friendly size
        
        #send start marker
        filelist_char.write(b"LIST_START", send_update=True)
        #send chunks
        for i in range(0, len(payload), CHUNK):
            part = payload[i:i+CHUNK]
            filelist_char.write(part, send_update=True)
            await asyncio.sleep_ms(20) # to avoid flooding
        #send end marker
        filelist_char.write(b"LIST_END", send_update=True)
    except Exception as e:
        print("Error sending file list", e)

   
async def filelist_task():
    #outer try-except to handle forceful BLE shutdown when recording
    try:
        while True:
            await filelist_char.written()
            if recording_active:
                await asyncio.sleep_ms(50)
                continue
            cmd = filelist_char.read().decode().strip()
            print("Filelist command received", cmd)
            
            if cmd == "LIST":
                await update_filelist_for_connection()
            await asyncio.sleep_ms(50)
    except asyncio.CancelledError:
        print("filelist_task cancelled")
        
        
#
#FOR DELETING FILES
#
# task: handle delete requests
async def delete_task():
    try:
        while True:
            #wait for write
            await delete_char.written()
            if recording_active:
                await asyncio.sleep_ms(50)
                continue
            filename = delete_char.read().decode("utf-8").strip()
            print("Delete request:", filename)
            
            #attempt to delete file
            try:
                uos.remove("/sd/" + filename)
                print("Deleted: ", filename)
            except Exception as e:
                print("Delete failed:", e)
            
            #push updated list
            await update_filelist_for_connection()
            
            await asyncio.sleep_ms(100)
    except asyncio.CancelledError:
        print("delete_task cancelled")
        
#
#FOR STREAMING AUDIO FILES
#

def read_ogg_page(f):
    header = f.read(27)
    if not header:
        return None
    if not header.startswith(b"OggS"):
        print("Invalid OGG header")
        return None
    
    seg_count = header[26]
    seg_table = f.read(seg_count)
    if len(seg_table) != seg_count:
        return None
    page_size = sum(seg_table)
    
    body = f.read(page_size)
    if len(body) != page_size:
        return None
    
    return header + seg_table + body

#task: wait for filename, open file and stream in chunks
#NOTE: this sends at ~6 KB/s
#CHUNK_BYTES = 68000
MAX_BYTES = 240000
BLE_PACKET = 128

async def audio_stream_task():
    current_file=None
    try:
        while True:
            #wait for a filename to be written
            await file_select_char.written()
            if recording_active:
                await asyncio.sleep_ms(50)
                continue
            filename = file_select_char.read().decode().strip()
            #Auto append .ogg if missing
            if not filename.lower().endswith(".ogg"):
                filename = filename + ".ogg"
                
            print("streaming request:", filename)
            
            #try opening the file
            try:
                current_file = open("/sd/" + filename, "rb")
            except Exception as e:
                print("Could not open file:", e)
                continue
            
            sent_total = 0
            while True:
                
                page = read_ogg_page(current_file)
                if not page:
                    break
                
                print("starting chunk stream")
                audio_stream_char.write(b"CHUNK_START", send_update=True)
                
                for i in range(0, len(page), BLE_PACKET):
                    print("CHUNK")
                    part = page[i:i+BLE_PACKET]
                    audio_stream_char.write(part, send_update=True)
                    sent_total += len(part)
                    
                    if sent_total >= MAX_BYTES:
                        break
                    await asyncio.sleep_ms(10)
                
                audio_stream_char.write(b"CHUNK_END", send_update=True)
                
                if sent_total >= MAX_BYTES:
                    break
                
            audio_stream_char.write(b"END", send_update=True)
            current_file.close()
            print("finished 30 second stream")
    except asyncio.CancelledError:
        print("audio_stream_task cancelled")
        

       
# global variables related to bluetooth shutdown control
current_connection = None
peripheral_task_handle = None
filelist_task_handle = None
delete_task_handle = None
audio_stream_task_handle = None
audio_transfer_task_handle = None

#helper function to cancel all BLE/SD tasks during recording
async def stop_ble_sd_tasks():
    global current_connection
    global peripheral_task_handle
    global filelist_task_handle, delete_task_handle
    global audio_stream_task_handle, audio_transfer_task_handle
    
    #make sure to disconnect active connections first
    if current_connection is not None:
        try:
            await current_connection.disconnect()
        except Exception as e:
            print("Error disconnecting current connection:", e)
            
    #hard stop any ongoing advertising
    try:
        ble.gap_advertising(None) #or ble.gap_advertise(0)
        print("Advertising stopped")
    except Exception as e:
        print("Error stopping advertising:", e)
        
    handles = [
        peripheral_task_handle,
        filelist_task_handle,
        delete_task_handle,
        audio_stream_task_handle,
        audio_transfer_task_handle,
    ]
    
    for h in handles:
        if h is not None:
            try:
                h.cancel()
            except:
                pass
    
    #give a buffer for them to exit
    await asyncio.sleep_ms(200)
    
    peripheral_task_handle = None
    filelist_task_handle = None
    delete_task_handle = None
    audio_stream_task_handle = None
    audio_transfer_task_handle = None
    
    #hard-disable BLE radio
    ble_off()
    

#and recreate them after recording is finished
async def start_ble_sd_tasks():
    global peripheral_task_handle
    global filelist_task_handle, delete_task_handle
    global audio_stream_task_handle, audio_transfer_task_handle
    
    #re-enable BLE radio + services
    ble_on()
    
    delete_task_handle = asyncio.create_task(delete_task())
    peripheral_task_handle = asyncio.create_task(peripheral_task())
    audio_stream_task_handle = asyncio.create_task(audio_stream_task())
    audio_transfer_task_handle = asyncio.create_task(audio_transfer_task())
    filelist_task_handle = asyncio.create_task(filelist_task())
    
_ADV_INTERVAL_MS = 100_000
#serially wait for connections, don't advertise when a central is connected
#advertises as a BLE service
async def peripheral_task():
    global current_connection
    #outer try-except handles bluetooth shutdown triggered by recording 
    try:
        
        while True:
            if recording_active:
                await asyncio.sleep_ms(100)
                continue
                #run a dummy advertiser that rejects all connections
#                 try:
#                     async with await aioble.advertise(
#                         _ADV_INTERVAL_MS,
#                         name="ResonateController1",
#                         services=[] #no services exposed
#                     ) as connection:
#                         print("Connection attempt during recording")
#                         try:
#                             await connection.disconnect()
#                             print("Rejected connection during recording")
#                         except:
#                             pass
#                 except asyncio.CancelledError:
#                     print("Peripheral task cancelled inside recording-mode advertise")
#                     raise
#                 except Exception as e:
#                     print("Error in recording-mode advertise:", e)
#                 await asyncio.sleep_ms(50)
#                 continue
#                 #force drop any incoming connections
#                 if current_connection is not None:
#                     try:
#                         await current_connection.disconnect()
#                         print("Rejected connection during recording")
#                     except:
#                         pass
#                 await asyncio.sleep_ms(50)
#                 continue
            #normal mode (not recording)
            try:
                async with await aioble.advertise(
                    _ADV_INTERVAL_MS,
                    name="ResonateController1",
                    services=[SERVICE1_UUID, SERVICE2_UUID, SERVICE3_UUID, _dummy_uuid],
                    ) as connection:
                        current_connection = connection
                        print("Connection from", connection.device)
                        
                        await connection.disconnected()
                        print("disconnected")
            except asyncio.CancelledError:
                print("Peripheral task cancelled inside advertise")
                raise #rethrow so outer try catches it
            except Exception as e:
                print("Error in peripheral_task:", e)
            finally:
                current_connection = None
                #make sure loop continues
                await asyncio.sleep_ms(100)
    except asyncio.CancelledError:
        print("Peripheral task fully cancelled")
        #clean exit


#
# MAIN CONTROL CODE
#
ledON = Pin(20, Pin.OUT)
ledON.value(1)
#global variable, when recording is active BLE/wifi should not be
recording_active = False
#run peripheral task and filelist task
async def main():
    global peripheral_task_handle
    global filelist_task_handle, delete_task_handle
    global audio_stream_task_handle, audio_transfer_task_handle
    
#     t1 = asyncio.create_task(delete_task())
#     peripheral_task_handle = asyncio.create_task(peripheral_task())
#     t3 = asyncio.create_task(audio_stream_task())
#     t4 = asyncio.create_task(audio_transfer_task())
#     t5 = asyncio.create_task(filelist_task())
#     t6 = asyncio.create_task(button_record_task())
    delete_task_handle = asyncio.create_task(delete_task())
    peripheral_task_handle = asyncio.create_task(peripheral_task())
    audio_stream_task_handle = asyncio.create_task(audio_stream_task())
    audio_transfer_task_handle = asyncio.create_task(audio_transfer_task())
    filelist_task_handle = asyncio.create_task(filelist_task())
    t_button = asyncio.create_task(button_record_task())
    
    await asyncio.gather(
        delete_task_handle,
        peripheral_task_handle,
        audio_stream_task_handle,
        audio_transfer_task_handle,
        filelist_task_handle,
        t_button,
    )

try:
    asyncio.run(main())
finally:
    #unmount sd card when finished
    uos.umount("/sd")
    print("SD unmounted")



