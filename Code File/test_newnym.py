import socket
socket.setdefaulttimeout(5)
import stem.control
try:
    print("Connecting...")
    with stem.control.Controller.from_port(port=9151) as controller:
        controller.authenticate()
        print("Connected! Sending NEWNYM...")
        controller.signal(stem.Signal.NEWNYM)
        print("Signal sent!")
except Exception as e:
    print("Error:", e)
